import jackpatch

from ..common import serializable
from core import Model, ModelList

from PySide.QtCore import *

# represent a unit, which can be connected to other units
class Unit(Model):
  def __init__(self, name='Unit', x=0, y=0, width=0, height=0):
    Model.__init__(self)
    self._name = name
    self._x = x
    self._y = y
    self._width = width
    self._height = height
  # get and set the name of the unit
  @property
  def name(self):
    return(self._name)
  @name.setter
  def name(self, value):
    if (value != self._name):
      self._name = value
      self.on_change()
  # get and set the position of the unit on the workspace
  @property
  def x(self):
    return(self._x)
  @x.setter
  def x(self, value):
    if (value != self._x):
      self._x = value
      self.on_change()
  @property
  def y(self):
    return(self._y)
  @y.setter
  def y(self, value):
    if (value != self._y):
      self._y = value
      self.on_change()
  # get and set the preferred size of the unit on the workspace 
  #  (which will not be respected by all unit types)
  @property
  def width(self):
    return(self._width)
  @width.setter
  def width(self, value):
    if (value != self._width):
      self._width = value
      self.on_change()
  @property
  def height(self):
    return(self._height)
  @height.setter
  def height(self, value):
    if (value != self._height):
      self._height = value
      self.on_change()
  # make a position and size interfaces for easy compatibility 
  #  with QGraphicsItem
  def pos(self):
    return(QPointF(self.x, self.y))
  def setPos(self, pos):
    self.x = pos.x()
    self.y = pos.y()
  def boundingRect(self):
    w = self.width
    h = self.height
    return(QRectF(- (w / 2), - (h / 2), w, h))
  def rect(self):
    w = self.width
    h = self.height
    return(QRectF(self.x - (w / 2), self.y - (h / 2), w, h))
  def setRect(self, rect):
    self.width = rect.width()
    self.height = rect.height()
    self.x = rect.x() + (rect.width() / 2)
    self.y = rect.y() + (rect.height() / 2)
  # unit serialization
  def serialize(self):
    obj = { 
      'name': self.name,
      'x': self.x,
      'y': self.y
    }
    if (self.width > 0):
      obj['width'] = self.width
    if (self.height > 0):
      obj['height'] = self.height
    return(obj)
serializable.add(Unit)

# represent a list of units
class UnitList(ModelList):
  def __init__(self, units=()):
    ModelList.__init__(self, units)
  # track serialization
  def serialize(self):
    return({ 
      'units': list(self)
    })
serializable.add(UnitList)

# make a mixin to make a model a signal source
class Source(object):
  def __init__(self):
    self._source_type = 'mono'
    self._source_port = None
  # return the type of signal emitted by this source
  @property
  def source_type(self):
    return(self._source_type)
  # get/set the JACK port or tuple of ports that send data
  @property
  def source_port(self):
    return(self._source_port)
  @source_port.setter
  def source_port(self, port):
    if (port is not self._source_port):
      self._source_port = port
      try:
        self.on_change()
      except AttributeError: pass

# make a mixin to make a model a signal sink
class Sink(object):
  def __init__(self):
    self._sink_type = 'mono'
    self._sink_port = None
  # return the type of signal emitted by this source
  @property
  def sink_type(self):
    return(self._sink_type)
  # get/set the JACK port or tuple of ports that accept data
  @property
  def sink_port(self):
    return(self._sink_port)
  @sink_port.setter
  def sink_port(self, port):
    if (port is not self._sink_port):
      self._sink_port = port
      try:
        self.on_change()
      except AttributeError: pass

# represent a connection between a source and sink
class Connection(Model):
  # keep a central JACK client for managing connections between ports
  jack_client = None
  def __init__(self, source=None, sink=None):
    Model.__init__(self)
    self._source = source
    self._sink = sink
    self._connected_source_port = None
    self._connected_sink_port = None
  @property
  def source(self):
    return(self._source)
  @source.setter
  def source(self, value):
    if (value is not self._source):
      if (self._source is not None):
        try:
          self._source.remove_observer(self.on_change)
        except AttributeError: pass
      self._source = value
      if (self._source is not None):
        try:
          self._source.add_observer(self.on_change)
        except AttributeError: pass
      self.on_change()
  @property
  def sink(self):
    return(self._sink)
  @sink.setter
  def sink(self, value):
    if (value is not self._sink):
      if (self._sink is not None):
        try:
          self._sink.remove_observer(self.on_change)
        except AttributeError: pass
      self._sink = value
      if (self._sink is not None):
        try:
          self._sink.add_observer(self.on_change)
        except AttributeError: pass
      self.on_change()
  # lazy-load a jack client to make patchbay connections
  def get_jack_client(self):
    if (Connection.jack_client is None):
      Connection.jack_client = jackpatch.Client('jackdaw-patchbay')
    return(Connection.jack_client)
  # propagate port and connection changes to JACK
  def on_change(self):
    source_port = self._source.source_port if (self._source is not None) else None
    sink_port = self._sink.sink_port if (self._sink is not None) else None
    if ((self._connected_source_port is not source_port) and 
        (self._connected_sink_port is not sink_port)):
      client = self.get_jack_client()
      if ((self._connected_source_port is not None) and 
          (self._connected_sink_port is not None)):
        client.disconnect(self._connected_source_port, 
                          self._connected_sink_port)
      if ((source_port is not None) and 
          (sink_port is not None)):
        client.connect(source_port, sink_port)
      self._connected_source_port = source_port
      self._connected_sink_port = sink_port
    # do normal change actions
    Model.on_change(self)
  # disconnect when deleted
  def __del__(self):
    if ((self._connected_source_port is not None) and 
          (self._connected_sink_port is not None)):
      client = self.get_jack_client()
      client.disconnect(self._connected_source_port, 
                        self._connected_sink_port)
  # connection serialization
  def serialize(self):
    return({ 
      'source': self.source,
      'sink': self.sink
    })
serializable.add(Connection)

# represent a patch bay that maintains connections between units
class PatchBay(ModelList):
  def __init__(self, connections=()):
    ModelList.__init__(self, connections)
  def invalidate(self):
    self._source_map = None
    self._sink_map = None
  # make a mapping that indexes sources by sink
  def _make_source_map(self):
    if (self._source_map is None):
      self._source_map = dict()
      for c in self:
        if (c.sink not in self._source_map):
          self._source_map[c.sink] = list()
        self._source_map[c.sink].append(c.source)
    return(self._source_map)
  # make a mapping that indexes sinks by source
  def _make_sink_map(self):
    if (self._sink_map is None):
      self._sink_map = dict()
      for c in self:
        if (c.source not in self._sink_map):
          self._sink_map[c.source] = list()
        self._sink_map[c.source].append(c.sink)
    return(self._sink_map)
  # get a list of all sinks connected to the given source
  def sources_for_sink(self, sink):
    m = self._make_source_map()
    if (sink in m):
      return(m[sink])
    return(())
  # get a list of all sources connected to the given sink
  def sinks_for_source(self, source):
    m = self._make_sink_map()
    if (source in m):
      return(m[source])
    return(())
    
  # TODO: prune connections with no source and/or sink
  
  def serialize(self):
    return({
      'connections': list(self)
    })
serializable.add(PatchBay)

# make a unit that represents the track list of the document
class MultitrackUnit(Unit):
  def __init__(self, tracks, view_scale, transport, *args, **kwargs):
    Unit.__init__(self, *args, **kwargs)
    self.tracks = tracks
    self.tracks.add_observer(self.on_change)
    self.transport = transport
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
  def serialize(self):
    obj = Unit.serialize(self)
    obj['tracks'] = self.tracks
    obj['transport'] = self.transport
    obj['view_scale'] = self.view_scale
    return(obj)
serializable.add(MultitrackUnit)

# make a unit that represents a list of MIDI devices
class DeviceListUnit(Unit):
  def __init__(self, devices, require_input=False, require_output=False, 
               *args, **kwargs):
    Unit.__init__(self, *args, **kwargs)
    self.devices = devices
    self.require_input = require_input
    self.require_output = require_output
    self.devices.add_observer(self.on_change)
  def serialize(self):
    obj = Unit.serialize(self)
    obj['devices'] = self.devices
    obj['require_input'] = self.require_input
    obj['require_output'] = self.require_output
    return(obj)
serializable.add(DeviceListUnit)

# make a unit that represents a list of sampler instruments
class InstrumentListUnit(Unit):
  def __init__(self, instruments, *args, **kwargs):
    Unit.__init__(self, *args, **kwargs)
    self.instruments = instruments
    self.instruments.add_observer(self.on_change)
  def serialize(self):
    obj = Unit.serialize(self)
    obj['instruments'] = self.instruments
    return(obj)
serializable.add(InstrumentListUnit)
