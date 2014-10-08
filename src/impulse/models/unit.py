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
  def __init__ (self):
    self._source_type = 'audio'
  # return the type of signal emitted by this source
  @property
  def source_type(self):
    return(self._source_type)

# make a mixin to make a model a signal sink
class Sink(object):
  def __init__ (self):
    self._sink_type = 'audio'
  # return the type of signal emitted by this source
  @property
  def sink_type(self):
    return(self._sink_type)

# represent a connection between a source and sink
class Connection(Model):
  def __init__(self, source=None, sink=None):
    Model.__init__(self)
    self._source = source
    self._sink = sink
  @property
  def source(self):
    return(self._source)
  @source.setter
  def source(self, value):
    if (value is not self._source):
      self._source = value
      self.on_change()
  @property
  def sink(self):
    return(self._sink)
  @sink.setter
  def sink(self, value):
    if (value is not self._sink):
      self._sink = value
      self.on_change()
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

# make a unit that represents the list of input devices
class DeviceListUnit(Unit):
  def __init__(self, devices, *args, **kwargs):
    Unit.__init__(self, *args, **kwargs)
    self.devices = devices
    self.devices.add_observer(self.on_change)
  def serialize(self):
    obj = Unit.serialize(self)
    obj['devices'] = self.devices
    return(obj)
serializable.add(DeviceListUnit)
