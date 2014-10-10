#include <Python.h>
#include "structmember.h"
#include <stdarg.h>
#include <jack/jack.h>

// the size of buffers to use for various purposes
#define BUFFER_SIZE 1024

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

// FORWARD DEFINITIONS ********************************************************

static PyTypeObject PortType;
typedef struct {
  PyObject_HEAD
  // public attributes
  PyObject *name;
  PyObject *client;
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
  // private stuff
  jack_client_t *_client;
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

static PyObject *
Client_close(Client *self) {
  if (self->_client != NULL) {
    jack_client_close(self->_client);
    self->_client = NULL;
    self->is_open = Py_False;
  }
  Py_RETURN_NONE;
}

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
  return(return_list);
}

static PyObject *
Client_connect(Client *self, PyObject *args, PyObject *kwds) {
  Port *source = NULL;
  Port *destination = NULL;
  static char *kwlist[] = {"source", "destination", NULL};
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!O!", kwlist, 
                                  &PortType, &source, &PortType, &destination))
    return(NULL);
  Client_open(self);
  if (self->_client == NULL) return(NULL);
  int result = jack_connect(self->_client, source->_port, destination->_port);
  if ((result == 0) || (result == EEXIST)) return(Py_True);
  else return(Py_False);
}

static void
Client_dealloc(Client* self) {
  Client_close(self);
  Py_XDECREF(self->name);  
  self->ob_type->tp_free((PyObject*)self);
}

static PyMemberDef Client_members[] = {
  {"name", T_OBJECT_EX, offsetof(Client, name), READONLY,
   "The client's unique name"},
  {"is_open", T_OBJECT_EX, offsetof(Client, is_open), READONLY,
   "Whether the client is connected to JACK"},
  {NULL}  /* Sentinel */
};

static PyMethodDef Client_methods[] = {
    {"open", (PyCFunction)Client_open, METH_NOARGS,
      "Ensure the client is connected to JACK"},
    {"close", (PyCFunction)Client_close, METH_NOARGS,
      "Ensure the client is not connected to JACK"},
    {"get_ports", (PyCFunction)Client_get_ports, METH_VARARGS | METH_KEYWORDS,
      "Get a list of available ports"},
    {"connect", (PyCFunction)Client_connect, METH_VARARGS | METH_KEYWORDS,
      "Connect a source and destination port"},
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
  PyObject *name = NULL, *tmp;
  Client *client = NULL;
  unsigned long flags = 0;
  static char *kwlist[] = { "client", "name", "flags", NULL };
  if (! PyArg_ParseTupleAndKeywords(args, kwds, "O!S|k", kwlist, 
                                    &ClientType, &client, &name, &flags))
    return(-1);
  tmp = self->name;
  Py_INCREF(name);
  self->name = name;
  Py_XDECREF(tmp);
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
  self->_port = jack_port_by_name(client->_client, PyString_AsString(name));
  // if there's no such port, we need to create one
  if (self->_port == NULL) {
    self->_is_mine = 1;
    self->_port = jack_port_register(
      client->_client, PyString_AsString(name), 
        JACK_DEFAULT_MIDI_TYPE, flags, 0);
  }
  if (self->_port == NULL) {
    _error("Failed to create a JACK port named \"%s\"", PyString_AsString(name));
    return(-1);
  }
  return(0);
}

static PyObject *
Port_send(Port *self, PyObject *args) {
  int status;
  static unsigned char midibuf[BUFFER_SIZE];
  PyObject *data;
  double time = 0.0;
  if (! PyArg_ParseTuple(args, "O|d", &data, &time)) return(NULL);
  if (! PySequence_Check(data)) {
    PyErr_SetString(PyExc_TypeError, 
      "Port.send expects argument 1 to be a sequence.");
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
  Py_RETURN_NONE;
}

static PyObject *
Port_receive(Port *self) {
  int status;
  static unsigned char midibuf[BUFFER_SIZE];
  
  Py_RETURN_NONE;
}

static PyMemberDef Port_members[] = {
  {"name", T_OBJECT_EX, offsetof(Port, name), READONLY,
   "The port's unique name"},
  {"client", T_OBJECT_EX, offsetof(Port, client), READONLY,
   "The client used to create the port"},
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
