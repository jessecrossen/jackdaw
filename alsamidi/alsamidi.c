#include <Python.h>
#include "structmember.h"
#include <stdarg.h>
#include <alsa/asoundlib.h>

// the size of buffers to use for various purposes
#define BUFFER_SIZE 1024

// handle errors and warnings
static PyObject *DeviceError;
static void _error(const char *format, ...) {
  static char message[BUFFER_SIZE];
  va_list ap;
  va_start(ap, format);
  vsnprintf(message, BUFFER_SIZE, format, ap);
  va_end(ap);
  PyErr_SetString(DeviceError, message);
}
static void _warn(const char *format, ...) {
  static char message[BUFFER_SIZE];
  va_list ap;
  va_start(ap, format);
  vsnprintf(message, BUFFER_SIZE, format, ap);
  va_end(ap);
  PyErr_WarnEx(PyExc_RuntimeWarning, message, 2);
}

typedef struct {
  PyObject_HEAD
  // public attributes
  PyObject *name;
  int client;
  int port;
  int is_input;
  int is_output;
  int is_connected;
  // private stuff
  snd_seq_t *_seq; // the sequencer handle of the open connection
  int _seq_port;   // the port used to connect with other clients
  int _queue;      // the queue id used for inbound event timing
  snd_midi_event_t *_codec; // a handle to convert ALSA evants <-> MIDI data
} Device;

static void
Device_dealloc(Device* self) {
  Py_XDECREF(self->name);
  if (self->_seq != NULL) snd_seq_close(self->_seq);
  if (self->_codec != NULL) snd_midi_event_free(self->_codec);
  self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
Device_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
  Device *self;
  self = (Device *)type->tp_alloc(type, 0);
  if (self != NULL) {
    self->name = Py_None;
    self->client = 0;
    self->port = 0;
    self->is_input = 0;
    self->is_output = 0;
    self->is_connected = 0;
    self->_seq = NULL;
    self->_seq_port = 0;
    self->_queue = SND_SEQ_QUEUE_DIRECT;
    self->_codec = NULL;
  }
  return((PyObject *)self);
}

static int
Device_init(Device *self, PyObject *args, PyObject *kwds) {
  PyObject *name=NULL, *tmp;
  static char *kwlist[] = {"name", "client", "port", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "|Oii", kwlist, 
                                    &name, &self->client, &self->port))
    return(-1);
  if (name) {
    tmp = self->name;
    Py_INCREF(name);
    self->name = name;
    Py_XDECREF(tmp);
  }
  return(0);
}

// get a connection to the sequencer
static snd_seq_t *_open_sequencer(int mode) {
  int status;
  snd_seq_t *seq;
  if ((status = snd_seq_open(&seq, "default", mode, 0)) < 0) {
    _error("Failed to open sequencer (%d): %s", 
      status, snd_strerror(status));
    return(NULL);
  }
  return(seq);
}

// get port info for a device
static snd_seq_port_info_t *_get_port_info(Device *self) {
  snd_seq_t *seq = self->_seq;
  if (seq == NULL) seq = _open_sequencer(SND_SEQ_OPEN_INPUT);
  if (seq == NULL) return(NULL);
  snd_seq_port_info_t *port_info;
  snd_seq_port_info_alloca(&port_info);
  int status = snd_seq_get_any_port_info(
    seq, self->client, self->port, port_info);
  if (status < 0) {
    _error("Failed to get port info for (%d:%d): %s",
      self->client, self->port, snd_strerror(status));
    snd_seq_close(seq);
    return(NULL);
  }
  if (seq != self->_seq) snd_seq_close(seq);
  return(port_info);
}
// transfer port info to the device's properties
void _update_from_port_info(Device *self, snd_seq_port_info_t *port_info) {
  int caps = snd_seq_port_info_get_capability(port_info);
  self->is_input = 
    ((caps & (SND_SEQ_PORT_CAP_READ|SND_SEQ_PORT_CAP_SUBS_READ)) != 0);
  self->is_output = 
    ((caps & (SND_SEQ_PORT_CAP_WRITE|SND_SEQ_PORT_CAP_SUBS_WRITE)) != 0);
}

static PyObject *
Device_probe(Device *self) {
  snd_seq_port_info_t *port_info = _get_port_info(self);
  if (port_info != NULL)
    _update_from_port_info(self, port_info);
  Py_RETURN_NONE;
}

static PyObject *
Device_connect(Device *self) {
  int status;
  // if already connected, there's nothing to do
  if (self->is_connected) return(Py_None);
  self->_seq = _open_sequencer(SND_SEQ_OPEN_DUPLEX | SND_SEQ_NONBLOCK);
  if (self->_seq == NULL) return(NULL);
  // create a queue for receiving events
  self->_queue = snd_seq_alloc_queue(self->_seq);
  if (self->_queue < 0) {
    _error("Failed to create a sequencer queue (%d): %s",
      status, snd_strerror(status));
    snd_seq_close(self->_seq);
    return(NULL);
  }
  // make a port to communicate on
  self->_seq_port = snd_seq_create_simple_port(self->_seq, "alsamidi",
      SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ |
      SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_SUBS_WRITE,
    SND_SEQ_PORT_TYPE_APPLICATION);
  // connect to the wrapped device
  if (self->is_input) {
    snd_seq_connect_from(self->_seq, self->_seq_port, 
      self->client, self->port);  
  }
  if (self->is_output) {
    snd_seq_connect_to(self->_seq, self->_seq_port, 
      self->client, self->port);  
  }
  // set up the port to timestamp all MIDI messages
  snd_seq_port_info_t *port_info;
  snd_seq_port_info_alloca(&port_info);
  snd_seq_get_port_info(self->_seq, self->_seq_port, port_info);
  snd_seq_port_info_set_timestamping(port_info, 1);
  snd_seq_port_info_set_timestamp_queue(port_info, self->_queue);
  snd_seq_port_info_set_timestamp_real(port_info, 1);
  snd_seq_set_port_info(self->_seq, self->_seq_port, port_info);
  // start the queue running
  status = snd_seq_start_queue(self->_seq, self->_queue, NULL);
  if (status < 0) {
    _error("Failed to start queue (%d): %s",
      status, snd_strerror(status));
    snd_seq_close(self->_seq);
    return(NULL);
  }
  snd_seq_drain_output(self->_seq);
  snd_seq_drop_input_buffer(self->_seq);
  // make an encoder/decoder for MIDI data
  snd_midi_event_new(BUFFER_SIZE, &self->_codec);
  self->is_connected = 1;
  Py_RETURN_NONE;
}

static PyObject *
Device_disconnect(Device *self) {
  int status;
  // if not connected, there's nothing to do
  if (! self->is_connected) return(Py_None);
  // free the encoder/decoder
  snd_midi_event_free(self->_codec);
  // stop the queue
  status = snd_seq_stop_queue(self->_seq, self->_queue, NULL);
  if (status < 0) {
    _warn("Failed to stop queue (%d): %s", status, snd_strerror(status));
  }
  // close the sequencer client
  status = snd_seq_close(self->_seq);
  if (status < 0) {
    _warn("Failed to close sequencer client (%d): %s", 
      status, snd_strerror(status));
  }
  // clear state
  self->_seq = NULL;
  self->_queue = 0;
  self->_seq_port = 0;
  self->_codec = NULL;
  self->is_connected = 0;
  Py_RETURN_NONE;
}

static PyObject *
Device_get_time(Device *self) {
  double time = 0.0;
  int status;
  if (! self->is_connected) return(Py_BuildValue("d", time));
  snd_seq_queue_status_t *queue_status;
  snd_seq_queue_status_alloca(&queue_status);
  status = snd_seq_get_queue_status(self->_seq, self->_queue, queue_status);
  if (status < 0) {
    _error("Failed to get queue status (%d): %s",
      status, snd_strerror(status));
    return(NULL);
  }
  const snd_seq_real_time_t *t = 
    snd_seq_queue_status_get_real_time(queue_status);
  time = (double)t->tv_sec + ((double)t->tv_nsec / 1000000000.0);
  return(Py_BuildValue("d", time));
}

static PyObject *
Device_send(Device *self, PyObject *args) {
  int status;
  static unsigned char midibuf[BUFFER_SIZE];
  PyObject *data;
  double time = 0.0;
  if (! PyArg_ParseTuple(args, "O|d", &data, &time)) return(NULL);
  if (! PySequence_Check(data)) {
    PyErr_SetString(PyExc_TypeError, 
      "Device.send expects argument 1 to be a sequence.");
  }
  if (! self->is_connected) {
    _error("Failed to send because there is no connection");
    return(NULL);
  }
  if (! self->is_output) {
    _error("Failed to send because this is not an output device");
    return(NULL);
  }
  size_t bytes = PySequence_Size(data);
  if (bytes > BUFFER_SIZE) bytes = BUFFER_SIZE;
  size_t i;
  unsigned char *c = midibuf;
  long value;
  for (i = 0; i < bytes; i++) {
    value = PyInt_AsLong(PySequence_ITEM(data, i));
    if ((value == -1) && (PyErr_Occurred())) return(NULL);
    *c = (value & 0xFF);
    c++;
  }
  // encode the raw MIDI data as an ALSA event
  snd_seq_event_t event;
  snd_midi_event_reset_encode(self->_codec);
  status = snd_midi_event_encode(self->_codec, midibuf, bytes, &event);
  if (status < 0) {
    _error("Failed to encode data as a MIDI event (%d): %s",
      status, snd_strerror(status));
    return(NULL);
  }
  // schedule the event at the given time
  long time_seconds = (long)floor(time);
  long time_nanoseconds = (long)((time - time_seconds) * 1000000000);
  event.time.time.tv_sec = time_seconds;
  event.time.time.tv_nsec = time_nanoseconds;
  // use the queue to schedule the output
  event.queue = self->_queue;
  // set the source to be the current client
  snd_seq_ev_set_source(&event, self->_seq_port);
  // all events except echo events should be broadcast to subscribers
  if (event.type != SND_SEQ_EVENT_ECHO) snd_seq_ev_set_subs(&event);
  // send the event
  snd_seq_event_output_direct(self->_seq, &event);
  Py_RETURN_NONE;
}

static PyObject *
Device_receive(Device *self) {
  int status;
  static unsigned char midibuf[BUFFER_SIZE];
  if (! self->is_connected) {
    _error("Failed to receive because there is no connection");
    return(NULL);
  }
  if (! self->is_input) {
    _error("Failed to receive because this is not an input device");
    return(NULL);
  }
  status = snd_seq_event_input_pending(self->_seq, 1);
  if (status <= 0) {
    Py_RETURN_NONE;
  }
  // fetch an event from the buffer
  snd_seq_event_t *event;
  status = snd_seq_event_input(self->_seq, &event);
  if (status == -ENOSPC) {
    _warn("alsamidi.Device: Input overrun on %d:%d\n",
      self->client, self->port);
  }
  else if (status < 0) {
    _error("Failed to get input from sequencer (%d): %s",
      status, snd_strerror(status));
    return(NULL);
  }
  // see if the event is an encodable MIDI event
  switch(event->type) {
    case (SND_SEQ_EVENT_NOTEOFF):
    case (SND_SEQ_EVENT_NOTEON):
    case (SND_SEQ_EVENT_KEYPRESS):
    case (SND_SEQ_EVENT_CONTROLLER):
    case (SND_SEQ_EVENT_PGMCHANGE):
    case (SND_SEQ_EVENT_CHANPRESS):
    case (SND_SEQ_EVENT_PITCHBEND):
    case (SND_SEQ_EVENT_SYSEX):
    case (SND_SEQ_EVENT_QFRAME):
    case (SND_SEQ_EVENT_SONGPOS):
    case (SND_SEQ_EVENT_SONGSEL):
    case (SND_SEQ_EVENT_TUNE_REQUEST):
    case (SND_SEQ_EVENT_CLOCK):
    case (SND_SEQ_EVENT_START):
    case (SND_SEQ_EVENT_CONTINUE):
    case (SND_SEQ_EVENT_STOP):
    case (SND_SEQ_EVENT_SENSING):
    case (SND_SEQ_EVENT_RESET):
    case (SND_SEQ_EVENT_CONTROL14):
    case (SND_SEQ_EVENT_NONREGPARAM):
    case (SND_SEQ_EVENT_REGPARAM):
      break;
    // handle the device getting unplugged
    case (SND_SEQ_EVENT_PORT_UNSUBSCRIBED):
      return(Device_disconnect(self));
    default:
      Py_RETURN_NONE;
  }
  // get event data as raw MIDI data
  snd_midi_event_reset_decode(self->_codec);
  long bytes = snd_midi_event_decode(
    self->_codec, midibuf, sizeof(midibuf), event);
  if (bytes < 0) {
    _error("Failed to decode ALSA event to MIDI data (%d): %s",
      bytes, snd_strerror(bytes));
    return(NULL);
  }
  // get the event time
  double time = (double)event->time.time.tv_sec + 
    ((double)event->time.time.tv_nsec / 1000000000.0);
  // package raw MIDI data into an array
  PyObject *data = PyList_New(bytes);
  unsigned char *c = midibuf;
  size_t i;
  for (i = 0; i < bytes; i++) {
    PyList_SET_ITEM(data, i, PyInt_FromLong(*c++));
  }
  PyObject *tuple = Py_BuildValue("(O,d)", data, time);
  Py_DECREF(data);
  return(tuple);
}

static PyMemberDef Device_members[] = {
  {"name", T_OBJECT_EX, offsetof(Device, name), 0,
   "A human readable device name"},
  {"client", T_INT, offsetof(Device, client), 0,
   "The client index of the device"},
  {"port", T_INT, offsetof(Device, port), 0,
   "The port number of the device"},
  {"is_input", T_INT, offsetof(Device, is_input), READONLY,
    "Whether the device is an input device"},
  {"is_output", T_INT, offsetof(Device, is_output), READONLY,
    "Whether the device is an output device"},
  {"is_connected", T_INT, offsetof(Device, is_connected), READONLY,
   "Whether the device is currently connected"},
  {NULL}  /* Sentinel */
};

static PyMethodDef Device_methods[] = {
    {"probe", (PyCFunction)Device_probe, METH_NOARGS,
      "Probe the device's capabilities without connecting to it. If a device is instantiated manually, this updates attributes like is_input and is_output. This does not need to be called if the device has been returned from alsamidi.get_devices()."},
    {"connect", (PyCFunction)Device_connect, METH_NOARGS,
      "Connect to the device for input and/or output"},
    {"disconnect", (PyCFunction)Device_disconnect, METH_NOARGS,
      "Disconnect from the device"},
    {"get_time", (PyCFunction)Device_get_time, METH_NOARGS,
      "Get the current real time of the device's clock, in seconds"},
    {"send", (PyCFunction)Device_send, METH_VARARGS,
      "Send a tuple of ints as a MIDI message to the device"},
    {"receive", (PyCFunction)Device_receive, METH_NOARGS,
      "Receive a MIDI message from the device"},
    {NULL}  /* Sentinel */
};

static PyTypeObject DeviceType = {
    PyObject_HEAD_INIT(NULL)
    0,                             /*ob_size*/
    "alsamidi.Device",             /*tp_name*/  
    sizeof(Device),                /*tp_basicsize*/
    0,                             /*tp_itemsize*/
    (destructor)Device_dealloc,    /*tp_dealloc*/
    0,                             /*tp_print*/
    0,                             /*tp_getattr*/
    0,                             /*tp_setattr*/
    0,                             /*tp_compare*/
    0,                             /*tp_repr*/
    0,                             /*tp_as_number*/
    0,                             /*tp_as_sequence*/
    0,                             /*tp_as_mapping*/
    0,                             /*tp_hash */
    0,                             /*tp_call*/
    0,                             /*tp_str*/
    0,                             /*tp_getattro*/
    0,                             /*tp_setattro*/
    0,                             /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Represents an ALSA MIDI device", /* tp_doc */
    0,		                         /* tp_traverse */
    0,		                         /* tp_clear */
    0,		                         /* tp_richcompare */
    0,		                         /* tp_weaklistoffset */
    0,		                         /* tp_iter */
    0,		                         /* tp_iternext */
    Device_methods,                /* tp_methods */
    Device_members,                /* tp_members */
    0,                             /* tp_getset */
    0,                             /* tp_base */
    0,                             /* tp_dict */
    0,                             /* tp_descr_get */
    0,                             /* tp_descr_set */
    0,                             /* tp_dictoffset */
    (initproc)Device_init,         /* tp_init */
    0,                             /* tp_alloc */
    Device_new,                    /* tp_new */
};

static PyObject *
alsamidi_get_devices(PyObject *self) {
  int status;
  // get a sequencer to list ports for
  snd_seq_t *seq = _open_sequencer(SND_SEQ_OPEN_INPUT);
  if (seq == NULL) return(NULL);
  // make a list of devices to return
  PyObject *return_list;
  return_list = PyList_New(0);
  // iterate through all clients
  snd_seq_client_info_t *client_info;
  snd_seq_client_info_alloca(&client_info);
  snd_seq_client_info_set_client(client_info, -1);
  // get info about ports on each client
  snd_seq_port_info_t *port_info;
  snd_seq_port_info_alloca(&port_info);
  while ((status = snd_seq_query_next_client(seq, client_info)) >= 0) {
    snd_seq_port_info_set_client(
      port_info, snd_seq_client_info_get_client(client_info));
    snd_seq_port_info_set_port(port_info, -1);
    while ((status = snd_seq_query_next_port(seq, port_info)) >= 0) {
      // get the device name
      const char *name = snd_seq_port_info_get_name(port_info);
      // skip our own client
      if (strncmp(name, "alsamidi", 8) == 0) continue;
      // make a device to add to the list
      Device *device = (Device *)Device_new(&DeviceType, NULL, NULL);
      if (device != NULL) {
        device->name = PyString_FromString(name);
        device->client = snd_seq_port_info_get_client(port_info);
        device->port = snd_seq_port_info_get_port(port_info);
        _update_from_port_info(device, port_info);
        if (PyList_Append(return_list, (PyObject *)device) < 0) {
          _error("Failed to append a device to the list");
          Py_DECREF(return_list);
          snd_seq_close(seq);
          return(NULL);
        }
      }
    }
  }
  if ((status < 0) && (PyList_Size(return_list) == 0)) {
    _error("Failed to get client/port info (%d): %s",
      status, snd_strerror(status));
    snd_seq_close(seq);
    Py_DECREF(return_list);
    return(NULL);
  }
  // close the connection to the sequencer
  snd_seq_close(seq);
  return(return_list);
}

// get a subscription from one device to another
static snd_seq_port_subscribe_t *
_fill_subscription(snd_seq_port_subscribe_t *subs, Device *source, Device *dest) {
  // add the source
  static snd_seq_addr_t source_addr;
  source_addr.client = source->client;
  source_addr.port = source->port;
  snd_seq_port_subscribe_set_sender(subs, &source_addr);
  // add the destination
  static snd_seq_addr_t dest_addr;
  dest_addr.client = dest->client;
  dest_addr.port = dest->port;
  snd_seq_port_subscribe_set_dest(subs, &dest_addr);
  return(subs);
}

static PyObject *
alsamidi_connect_devices(PyObject *self, PyObject *args, PyObject *kwds) {
  int status;
  Device *source = NULL;
  Device *dest = NULL;
  static char *kwlist[] = {"source", "dest", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!O!", kwlist, 
                                    &DeviceType, &source, &DeviceType, &dest))
    return(NULL);
  // get a subscription between the ports
  snd_seq_port_subscribe_t *subs;
  snd_seq_port_subscribe_alloca(&subs);
  _fill_subscription(subs, source, dest);
  // open a sequencer client to do the work
  snd_seq_t *seq = _open_sequencer(SND_SEQ_OPEN_DUPLEX);
  if (seq == NULL) return(NULL);
  // if there is already such a connection, there's nothing to do
  if (snd_seq_get_port_subscription(seq, subs) >= 0) {
    snd_seq_close(seq);
    Py_RETURN_NONE;
  }
  // make the connection
  status = snd_seq_subscribe_port(seq, subs);
  if (status < 0) {
    _error("Failed to connect devices (%d): %s",
      status, snd_strerror(status));
    snd_seq_close(seq);
    return(NULL);
  }
  // clean up
  snd_seq_close(seq);
  Py_RETURN_NONE;
}

static PyObject *
alsamidi_disconnect_devices(PyObject *self, PyObject *args, PyObject *kwds) {
  int status;
  Device *source = NULL;
  Device *dest = NULL;
  static char *kwlist[] = {"source", "dest", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!O!", kwlist, 
                                    &DeviceType, &source, &DeviceType, &dest))
    return(NULL);
  // get a subscription between the ports
  snd_seq_port_subscribe_t *subs;
  snd_seq_port_subscribe_alloca(&subs);
  _fill_subscription(subs, source, dest);
  // open a sequencer client to do the work
  snd_seq_t *seq = _open_sequencer(SND_SEQ_OPEN_DUPLEX);
  if (seq == NULL) return(NULL);
  // if there is no such connection, don't treat it as an error,
  //  because the desired state has been reached
  if (snd_seq_get_port_subscription(seq, subs) < 0) {
    snd_seq_close(seq);
    Py_RETURN_NONE;
  }
  status = snd_seq_unsubscribe_port(seq, subs);
  if (status < 0) {
    _error("Failed to disconnect devices (%d): %s",
      status, snd_strerror(status));
    snd_seq_close(seq);        
    return(NULL);
  }
  snd_seq_close(seq);
  Py_RETURN_NONE;
}

static PyMethodDef alsamidi_methods[] = {
    {"get_devices",  alsamidi_get_devices, METH_NOARGS,
     "Get a list of available MIDI devices."},
    {"connect_devices",  
      alsamidi_connect_devices, METH_VARARGS|METH_KEYWORDS,
     "Add a connection between two devices."},
    {"disconnect_devices",  
      alsamidi_disconnect_devices, METH_VARARGS|METH_KEYWORDS,
     "Remove a connection between two devices."},
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initalsamidi(void) {
  PyObject* m;

  DeviceType.tp_new = PyType_GenericNew;
  if (PyType_Ready(&DeviceType) < 0)
      return;

  m = Py_InitModule3("alsamidi", alsamidi_methods,
                     "A Pythonic wrapper for the ALSA Sequencer supporting virtual devices and hotplugging");

  DeviceError = PyErr_NewException("alsamidi.DeviceError", NULL, NULL);
  Py_INCREF(DeviceError);
  PyModule_AddObject(m, "DeviceError", DeviceError);

  Py_INCREF(&DeviceType);
  PyModule_AddObject(m, "Device", (PyObject *)&DeviceType);
}
