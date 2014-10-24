#include <Python.h>
#include "structmember.h"
#include <stdarg.h>

#include <jack/jack.h>
#include <jack/midiport.h>

// the size of buffers to use for various purposes
#define BUFFER_SIZE 1024
// the maximum number of MIDI I/O ports to allow for a client
#define MAX_PORTS_PER_CLIENT 256
// define whether to emit warnings when in a JACK processing callback
//  (normally not a great idea because it can produce floods of warnings, but 
//   useful when debugging)
#define WARN_IN_PROCESS 1

// ERROR HANDLING *************************************************************

static PyObject *JackError;
static void _error(const char *format, ...) {
  static char message[BUFFER_SIZE];
  va_list ap;
  va_start(ap, format);
  vsnprintf(message, BUFFER_SIZE, format, ap);
  va_end(ap);
  PyErr_SetString(JackError, message);
}
static void _warn(const char *format, ...) {
  static char message[BUFFER_SIZE];
  va_list ap;
  va_start(ap, format);
  vsnprintf(message, BUFFER_SIZE, format, ap);
  va_end(ap);
  PyErr_WarnEx(PyExc_RuntimeWarning, message, 2);
}

// MIDI MESSAGE QUEUE *********************************************************

// define a struct to store queued MIDI messages, with a self-pointer that can
//  be used to manage the queue as a linked list
typedef struct {
  void *next;
  jack_port_t *port;
  jack_nframes_t time;
  size_t data_size;
  // the data goes at the end so we can allocate a variable number of bytes 
  //  for it depending on the message length; if you want to add more members
  //  to the struct, do it somewhere above here
  unsigned char data[];
} Message;

// FORWARD DEFINITIONS ********************************************************

static PyTypeObject PortType;
typedef struct {
  PyObject_HEAD
  // public attributes
  PyObject *name;
  PyObject *client;
  PyObject *flags;
  // private stuff
  jack_port_t *_port;
  int _is_mine;
} Port;

static PyTypeObject ClientType;
typedef struct {
  PyObject_HEAD
  // public attributes
  PyObject *name;
  PyObject *is_open;
  PyObject *is_active;
  // private stuff
  jack_client_t *_client;
  int _send_port_count;
  jack_port_t **_send_ports;
  Message *_midi_send_queue_head;
  int _receive_port_count;
  jack_port_t **_receive_ports;
  Message *_midi_receive_queue_head;
  Message *_midi_receive_queue_tail;
} Client;

static PyObject * Port_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
static int Port_init(Port *self, PyObject *args, PyObject *kwds);

// CLIENT *********************************************************************

static PyObject *
Client_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
  Client *self;
  self = (Client *)type->tp_alloc(type, 0);
  if (self != NULL) {
    self->name = Py_None;
    self->is_open = Py_False;
    self->is_active = Py_False;
    self->_send_port_count = 0;
    self->_send_ports = malloc(sizeof(jack_port_t *) * MAX_PORTS_PER_CLIENT);
    self->_midi_send_queue_head = NULL;
    self->_receive_port_count = 0;
    self->_receive_ports = malloc(sizeof(jack_port_t *) * MAX_PORTS_PER_CLIENT);
    self->_midi_receive_queue_head = NULL;
    self->_midi_receive_queue_tail = NULL;
  }
  return((PyObject *)self);
}

static int
Client_init(Client *self, PyObject *args, PyObject *kwds) {
  PyObject *name=NULL, *tmp;
  static char *kwlist[] = {"name", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "S", kwlist, 
                                    &name))
    return(-1);
  tmp = self->name;
  Py_INCREF(name);
  self->name = name;
  Py_XDECREF(tmp);
  return(0);
}

// make sure the client is connected to the JACK server
static PyObject *
Client_open(Client *self) {
  if (self->_client == NULL) {
    jack_status_t status;
    self->_client = jack_client_open(PyString_AsString(self->name), 
      JackNoStartServer, &status);
    if ((status & JackServerFailed) != 0) {
      _error("%s", "Failed to connect to the JACK server");
      return(NULL);
    }
    else if ((status & JackServerError) != 0) {
      _error("%s", "Failed to communicate with the JACK server");
      return(NULL);
    }
    else if ((status & JackFailure) != 0) {
      _error("%s", "Failed to create a JACK client");
      return(NULL);
    }
    self->is_open = Py_True;
  }
  Py_RETURN_NONE;
}

// close a client's connection to JACK server
static PyObject *
Client_close(Client *self) {
  if (self->_client != NULL) {
    jack_client_close(self->_client);
    self->_client = NULL;
    self->is_open = Py_False;
  }
  Py_RETURN_NONE;
}

// send queued messages for one of a client's ports
static void
Client_send_messages_for_port(Client *self, jack_port_t *port, 
                              jack_nframes_t nframes) {
  unsigned char *buffer;
  // get a writable buffer for the port
  void *port_buffer = jack_port_get_buffer(port, nframes);
  if (port_buffer == NULL) {
    #ifdef WARN_IN_PROCESS
      _warn("Failed to get port buffer for sending");
    #endif
    return;
  }
  // clear the buffer for writing
  jack_midi_clear_buffer(port_buffer);
  // send messages
  Message *last = NULL;
  Message *message = self->_midi_send_queue_head;
  Message *next = NULL;
  int port_send_count = 0;
  jack_nframes_t last_time = 0;
  while (message != NULL) {
    // get messages for the current port
    if (message->port == port) {
      // if this message overlaps with another's time, 
      //  delay it enough that they don't overlap
      if ((port_send_count > 0) && (message->time <= last_time)) {
        message->time = last_time + 1;
      }
      // get messages that fall in the current block
      if (message->time < nframes) {
        buffer = jack_midi_event_reserve(
          port_buffer, message->time, message->data_size);
        if (buffer != NULL) {
          memcpy(buffer, message->data, message->data_size);
        }
        else {
          #ifdef WARN_IN_PROCESS
            _warn("Failed to allocate a buffer to write a message into");
          #endif
        }
        // keep track of the time of the last message
        port_send_count++;
        last_time = message->time;
        // remove the message from the queue once sent
        next = (Message *)message->next;
        message->next = NULL;
        if (last != NULL) last->next = next;
        if (message == self->_midi_send_queue_head) {
          self->_midi_send_queue_head = next;
        }
        free(message);
        message = next;
        continue;
      }
      // shift the times of remaining messages so they get sent in later blocks
      message->time -= nframes;
    }
    // traverse the linked list
    last = message;
    message = (Message *)message->next;
  }
}

// receive and enqueue messages for one of a client's ports
static void
Client_receive_messages_for_port(Client *self, jack_port_t *port, 
                                 jack_nframes_t nframes) {
  int result;
  Message *message = NULL;
  // get a readable buffer for the port
  void *port_buffer = jack_port_get_buffer(port, nframes);
  if (port_buffer == NULL) {
    #ifdef WARN_IN_PROCESS
      _warn("Failed to get port buffer for receiving");
    #endif
    return;
  }
  // get the number of events to receive for this block
  int event_count = jack_midi_get_event_count(port_buffer);
  jack_midi_event_t event;
  // receive events
  for (int i = 0; i < event_count; i++) {
    result = jack_midi_event_get(&event, port_buffer, i);
    if (result != 0) {
      #ifdef WARN_IN_PROCESS
        _warn("Failed to get an event at index %d", i);
      #endif
      continue;
    }
    // allocate a message to store the event
    message = (Message *)malloc(sizeof(Message) + 
                (sizeof(unsigned char) * event.size));
    if (message == NULL) {
      #ifdef WARN_IN_PROCESS
        _warn("Failed to allocate memory for the message at index %d "
              "with data size %d", i, event.size);
      #endif
      continue;
    }
    // set up the message
    message->next = NULL;
    message->port = port;
    // TODO: add transport time
    message->time = event.time;
    message->data_size = event.size;
    memcpy(message->data, event.buffer, event.size);
    // attach it to the queue
    if (self->_midi_receive_queue_head == NULL) {
      self->_midi_receive_queue_head = message;
    }
    if (self->_midi_receive_queue_tail != NULL) {
      self->_midi_receive_queue_tail->next = message;
    }
    self->_midi_receive_queue_tail = message;
  }
}

// process a block of events for a client
static int
Client_process(jack_nframes_t nframes, void *self_ptr) {
  int i;
  jack_port_t *port;
  Client *self = (Client *)self_ptr;
  if (self == NULL) return(-1);
  // send queued messages
  for (i = 0; i < self->_send_port_count; i++) {
    port = self->_send_ports[i];
    Client_send_messages_for_port(self, port, nframes);
  }
  // enqueue received messages
  for (i = 0; i < self->_receive_port_count; i++) {
    port = self->_receive_ports[i];
    Client_receive_messages_for_port(self, port, nframes);
  }
  return(0);
}

// start processing events for a client
static PyObject *
Client_activate(Client *self) {
  int result;
  Client_open(self);
  if (self->_client == NULL) return(NULL);
  if (self->is_active != Py_True) {
    // connect a callback for processing MIDI messages
    result = jack_set_process_callback(self->_client, Client_process, self);
    if (result != 0) {
      _warn("Failed to set a callback for the JACK client (error %i), "
            "MIDI send/receive will be disabled", result);
    }
    result = jack_activate(self->_client);
    if (result != 0) {
      _error("Failed to activate the JACK client (error %i)", result);
      return(NULL);
    }
    self->is_active = Py_True;
  }
  Py_RETURN_NONE;
}

// stop processing events for a client
static PyObject *
Client_deactivate(Client *self) {
  if ((self->is_active == Py_True) && (self->_client != NULL)) {
    int result = jack_deactivate(self->_client);
    if (result != 0) {
      _error("Failed to deactivate the JACK client (error %i)", result);
      return(NULL);
    }
    self->is_active = Py_False;
  }
  Py_RETURN_NONE;
}

// use a client to list ports (this will also list ports owned by other clients)
static PyObject *
Client_get_ports(Client *self, PyObject *args, PyObject *kwds) {
  const char *name_pattern = NULL;
  const char *type_pattern = NULL;
  unsigned long flags = 0;
  static char *kwlist[] = {"name_pattern", "type_pattern", "flags", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "|ssk", kwlist, 
                                    &name_pattern, &type_pattern, &flags))
    return(NULL);
  // make sure we're connected to JACK
  Client_open(self);
  if (self->_client == NULL) return(NULL);
  // get a list of port names
  const char **port_name = jack_get_ports(self->_client, 
    name_pattern, type_pattern, flags); 
  // convert the port names into a list of Port objects
  PyObject *return_list;
  return_list = PyList_New(0);
  if (port_name != NULL) {
    while (*port_name != NULL) {
      Port *port = (Port *)Port_new(&PortType, NULL, NULL);
      if (port != NULL) {
        PyObject *name = PyString_FromString(*port_name);
        Port_init(port, Py_BuildValue("(O,S)", self, name), Py_BuildValue("{}"));
        if (PyList_Append(return_list, (PyObject *)port) < 0) {
          _error("Failed to append a port to the list");
          Py_DECREF(return_list);
          return(NULL);
        }
      }
      port_name++;
    }
  }
  return(return_list);
}

// use a client to make a connection between two ports
static PyObject *
Client_connect(Client *self, PyObject *args, PyObject *kwds) {
  Port *source = NULL;
  Port *destination = NULL;
  static char *kwlist[] = {"source", "destination", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!O!", kwlist, 
                                  &PortType, &source, &PortType, &destination))
    return(NULL);
  Client_activate(self);
  if (self->is_active != Py_True) return(NULL);
  int result = jack_connect(self->_client, 
    PyString_AsString(source->name), 
    PyString_AsString(destination->name));
  if ((result == 0) || (result == EEXIST)) Py_RETURN_TRUE;
  else {
    _warn("Failed to connect JACK ports (error %i)", result);
    Py_RETURN_FALSE;
  }
}

// use a client to break the connection between two ports, if any
static PyObject *
Client_disconnect(Client *self, PyObject *args, PyObject *kwds) {
  Port *source = NULL;
  Port *destination = NULL;
  static char *kwlist[] = {"source", "destination", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!O!", kwlist, 
                                  &PortType, &source, &PortType, &destination))
    return(NULL);
  Client_activate(self);
  if (self->is_active != Py_True) return(NULL);
  int result = jack_disconnect(self->_client, 
    PyString_AsString(source->name), 
    PyString_AsString(destination->name));
  if ((result == 0) || (result == EEXIST)) Py_RETURN_TRUE;
  else {
    _warn("Failed to disconnect JACK ports (error %i)", result);
    Py_RETURN_FALSE;
  }
}

// clean up allocated data for a client
static void
Client_dealloc(Client* self) {
  Client_close(self);
  // invalidate references to ports by zeroing the counts
  self->_send_port_count = 0;
  self->_receive_port_count = 0;
  // remove all events from the send and receive queues
  Message *message = NULL;
  Message *next = NULL;
  message = self->_midi_receive_queue_head;
  self->_midi_receive_queue_head = NULL;
  self->_midi_receive_queue_tail = NULL;
  while (message != NULL) {
    next = message->next;
    free(message);
    message = next;
  }
  message = self->_midi_send_queue_head;
  self->_midi_send_queue_head = NULL;
  while (message != NULL) {
    next = message->next;
    free(message);
    message = next;
  }
  Py_XDECREF(self->name);  
  self->ob_type->tp_free((PyObject*)self);
}

static PyMemberDef Client_members[] = {
  {"name", T_OBJECT_EX, offsetof(Client, name), READONLY,
   "The client's unique name"},
  {"is_open", T_OBJECT_EX, offsetof(Client, is_open), READONLY,
   "Whether the client is connected to JACK"},
  {"is_active", T_OBJECT_EX, offsetof(Client, is_active), READONLY,
   "Whether the client is activated to send and receive data"},
  {NULL}  /* Sentinel */
};

static PyMethodDef Client_methods[] = {
    {"open", (PyCFunction)Client_open, METH_NOARGS,
      "Ensure the client is connected to JACK"},
    {"close", (PyCFunction)Client_close, METH_NOARGS,
      "Ensure the client is not connected to JACK"},
    {"activate", (PyCFunction)Client_activate, METH_NOARGS,
      "Ensure the client is ready to send and receive data"},
    {"deactivate", (PyCFunction)Client_deactivate, METH_NOARGS,
      "Ensure the client cannot send and receive data"},
    {"get_ports", (PyCFunction)Client_get_ports, METH_VARARGS | METH_KEYWORDS,
      "Get a list of available ports"},
    {"connect", (PyCFunction)Client_connect, METH_VARARGS | METH_KEYWORDS,
      "Connect a source and destination port"},
    {"disconnect", (PyCFunction)Client_disconnect, METH_VARARGS | METH_KEYWORDS,
      "Disconnect a source and destination port"},
    {NULL, NULL, 0, NULL}  /* Sentinel */
};

static PyTypeObject ClientType = {
    PyObject_HEAD_INIT(NULL)
    0,                             /*ob_size*/
    "jackpatch.Client",            /*tp_name*/  
    sizeof(Client),                /*tp_basicsize*/
    0,                             /*tp_itemsize*/
    (destructor)Client_dealloc,    /*tp_dealloc*/
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
    "Represents a JACK client",    /* tp_doc */
    0,		                         /* tp_traverse */
    0,		                         /* tp_clear */
    0,		                         /* tp_richcompare */
    0,		                         /* tp_weaklistoffset */
    0,		                         /* tp_iter */
    0,		                         /* tp_iternext */
    Client_methods,                /* tp_methods */
    Client_members,                /* tp_members */
    0,                             /* tp_getset */
    0,                             /* tp_base */
    0,                             /* tp_dict */
    0,                             /* tp_descr_get */
    0,                             /* tp_descr_set */
    0,                             /* tp_dictoffset */
    (initproc)Client_init,         /* tp_init */
    0,                             /* tp_alloc */
    Client_new,                    /* tp_new */
};


// PORT ***********************************************************************

static void
Port_dealloc(Port* self) {
  Py_XDECREF(self->name);
  Py_XDECREF(self->client);
  self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
Port_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
  Port *self;
  self = (Port *)type->tp_alloc(type, 0);
  if (self != NULL) {
    self->name = Py_None;
  }
  return((PyObject *)self);
}

static int
Port_init(Port *self, PyObject *args, PyObject *kwds) {
  char *requested_name = NULL;
  PyObject *name = NULL, *tmp;
  Client *client = NULL;
  unsigned long flags = 0;
  static char *kwlist[] = { "client", "name", "flags", NULL };
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!s|k", kwlist, 
                                    &ClientType, &client, &requested_name, &flags))
    return(-1);
  // hold a reference to the underlying client so it never goes away while its
  //  ports are being used
  PyObject *client_obj = (PyObject *)client;
  tmp = self->client;
  Py_INCREF(client_obj);
  self->client = client_obj;
  Py_XDECREF(tmp);
  // make sure the client is connected
  Client_open(client);
  if (client->_client == NULL) return(-1);
  // see if a port already exists with this name
  self->_is_mine = 0;
  self->_port = jack_port_by_name(client->_client, requested_name);
  // if there's no such port, we need to create one
  if (self->_port == NULL) {
    self->_is_mine = 1;
    self->_port = jack_port_register(
      client->_client, requested_name, 
        JACK_DEFAULT_MIDI_TYPE, flags, 0);
    // store the port with the client so it can manage MIDI for it
    if ((flags & JackPortIsInput) != 0) {
      if (client->_receive_port_count >= MAX_PORTS_PER_CLIENT) {
        _warn("Failed to manage the port named \"%s\" because client has "
              "too many ports. MIDI will be disabled for that port.", 
              jack_port_name(self->_port));
      }
      else {
        client->_receive_ports[client->_receive_port_count] = self->_port;
        client->_receive_port_count++;
      }
    }
    else if ((flags & JackPortIsOutput) != 0) {
      if (client->_send_port_count >= MAX_PORTS_PER_CLIENT) {
        _warn("Failed to manage the port named \"%s\" because client has "
              "too many ports. MIDI will be disabled for that port.", 
              jack_port_name(self->_port));
      }
      else {
        client->_send_ports[client->_send_port_count] = self->_port;
        client->_send_port_count++;
      }
    }
  }
  if (self->_port == NULL) {
    _error("Failed to create a JACK port named \"%s\"", requested_name);
    return(-1);
  }
  // store the actual name of the port
  tmp = self->name;
  self->name = PyString_FromString(jack_port_name(self->_port));
  Py_XDECREF(tmp);
  // store the actual flags of the port
  tmp = self->flags;
  self->flags = Py_BuildValue("i", jack_port_flags(self->_port));
  Py_XDECREF(tmp);
  return(0);
}

static PyObject *
Port_send(Port *self, PyObject *args) {
  int status;
  PyObject *data;
  double time = 0.0;
  if (! PyArg_ParseTuple(args, "O|d", &data, &time)) return(NULL);
  if (! PySequence_Check(data)) {
    PyErr_SetString(PyExc_TypeError, 
      "Port.send expects argument 1 to be a sequence");
  }
  // the client needs to be activated for sending to work
  Client *client = (Client *)self->client;
  Client_activate(client);
  // get the current sample rate for time conversions
  jack_nframes_t sample_rate = jack_get_sample_rate(client->_client);
  // store the message
  size_t bytes = PySequence_Size(data);
  Message *message = malloc(sizeof(Message) + (sizeof(unsigned char) * bytes));
  if (message == NULL) {
    _error("Failed to allocate memory for MIDI data");
    return(NULL);
  }
  message->next = NULL;
  message->port = self->_port;
  message->time = (jack_nframes_t)(time * (double)sample_rate);
  message->data_size = bytes;
  unsigned char *mdata = message->data;
  long value;
  for (size_t i = 0; i < bytes; i++) {
    value = PyInt_AsLong(PySequence_ITEM(data, i));
    if ((value == -1) && (PyErr_Occurred())) return(NULL);
    *mdata = (unsigned char)(value & 0xFF);
    mdata++;
  }
  // if the queue is empty, begin it with the message
  if (client->_midi_send_queue_head == NULL) {
    client->_midi_send_queue_head = message;
  }
  else {
    // insert the message to the client's send queue in whatever position
    //  keeps the queue sorted by time
    Message *last = NULL;
    Message *current = client->_midi_send_queue_head;
    // store the message time to save lookups
    jack_nframes_t mtime = message->time;
    while (current != NULL) {
      // if we find an existing message that comes after this one, insert this
      //  one before it
      if (mtime < current->time) {
        if (last == NULL) {
          client->_midi_send_queue_head = message;
        }
        else {
          last->next = message;
        }
        message->next = current;
        // clear the message to indicate it's been stored in the queue
        message = NULL;
        break;
      }
      // advance to the next message
      last = current;
      current = (Message *)current->next;
    }
    // if we get to the end and the message hasn't been inserted, 
    //  insert it after the last message we have
    if ((message != NULL) && (last != NULL)) {
      last->next = message;
    }
  }
  Py_RETURN_NONE;
}

static PyObject *
Port_receive(Port *self) {
  // the client needs to be activated for receiving to work
  Client *client = (Client *)self->client;
  Client_activate(client);
  // get the current sample rate for time conversions
  jack_nframes_t sample_rate = jack_get_sample_rate(client->_client);
  // pull events from the receive queue for the client
  Message *last = NULL;
  Message *message = client->_midi_receive_queue_head;
  Message *next = NULL;
  jack_port_t *port = self->_port;
  while (message != NULL) {
    // get all messages for this port
    if (message->port == port) {
      // convert the event time from samples to seconds
      double time = (double)message->time / (double)sample_rate;
      // package raw MIDI data into an array
      size_t bytes = message->data_size;
      PyObject *data = PyList_New(bytes);
      unsigned char *c = message->data;
      size_t i;
      for (i = 0; i < bytes; i++) {
        PyList_SET_ITEM(data, i, PyInt_FromLong(*c++));
      }
      PyObject *tuple = Py_BuildValue("(O,d)", data, time);
      Py_DECREF(data);
      // remove the message from the queue once received
      next = (Message *)message->next;
      message->next = NULL;
      if (last != NULL) last->next = next;
      if (message == client->_midi_receive_queue_head) {
        client->_midi_receive_queue_head = next;
      }
      if (message == client->_midi_receive_queue_tail) {
        client->_midi_receive_queue_tail = last;
      }
      free(message);
      // return the message
      return(tuple);
    }
    last = message;
    message = (Message *)message->next;
  }
  // if we get here, there were no messages for this port
  Py_RETURN_NONE;
}

static PyMemberDef Port_members[] = {
  {"name", T_OBJECT_EX, offsetof(Port, name), READONLY,
   "The port's unique name"},
  {"client", T_OBJECT_EX, offsetof(Port, client), READONLY,
   "The client used to create the port"},
  {"flags", T_OBJECT_EX, offsetof(Port, flags), READONLY,
   "The port's flags as a bitfield of JackPortFlags"},
  {NULL}  /* Sentinel */
};

static PyMethodDef Port_methods[] = {
    {"send", (PyCFunction)Port_send, METH_VARARGS,
      "Send a tuple of ints as a MIDI message to the port"},
    {"receive", (PyCFunction)Port_receive, METH_NOARGS,
      "Receive a MIDI message from the port"},
    {NULL, NULL, 0, NULL}  /* Sentinel */
};

static PyTypeObject PortType = {
    PyObject_HEAD_INIT(NULL)
    0,                             /*ob_size*/
    "jackpatch.Port",              /*tp_name*/  
    sizeof(Port),                  /*tp_basicsize*/
    0,                             /*tp_itemsize*/
    (destructor)Port_dealloc,      /*tp_dealloc*/
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
    "Represents an JACK port",     /* tp_doc */
    0,		                         /* tp_traverse */
    0,		                         /* tp_clear */
    0,		                         /* tp_richcompare */
    0,		                         /* tp_weaklistoffset */
    0,		                         /* tp_iter */
    0,		                         /* tp_iternext */
    Port_methods,                  /* tp_methods */
    Port_members,                  /* tp_members */
    0,                             /* tp_getset */
    0,                             /* tp_base */
    0,                             /* tp_dict */
    0,                             /* tp_descr_get */
    0,                             /* tp_descr_set */
    0,                             /* tp_dictoffset */
    (initproc)Port_init,           /* tp_init */
    0,                             /* tp_alloc */
    Port_new,                      /* tp_new */
};

// MODULE *********************************************************************

static PyMethodDef jackpatch_methods[] = {
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initjackpatch(void) {
  PyObject* m;

  PortType.tp_new = PyType_GenericNew;
  if (PyType_Ready(&ClientType) < 0)
      return;
  if (PyType_Ready(&PortType) < 0)
      return;

  m = Py_InitModule3("jackpatch", jackpatch_methods,
                     "A Pythonic wrapper for the JACK audio connection kit's MIDI and patchbay functionality");

  JackError = PyErr_NewException("jackpatch.JackError", NULL, NULL);
  Py_INCREF(JackError);
  PyModule_AddObject(m, "JackError", JackError);

  // add constants
  PyModule_AddIntConstant(m, "JackPortIsInput", JackPortIsInput);
  PyModule_AddIntConstant(m, "JackPortIsOutput", JackPortIsOutput);
  PyModule_AddIntConstant(m, "JackPortIsPhysical", JackPortIsPhysical);
  PyModule_AddIntConstant(m, "JackPortCanMonitor", JackPortCanMonitor);
  PyModule_AddIntConstant(m, "JackPortIsTerminal", JackPortIsTerminal);

  // add classes
  Py_INCREF(&ClientType);
  PyModule_AddObject(m, "Client", (PyObject *)&ClientType);
  Py_INCREF(&PortType);
  PyModule_AddObject(m, "Port", (PyObject *)&PortType);
}
