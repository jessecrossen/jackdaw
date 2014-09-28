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

# represent a connection between two objects
class Connection(Model):
  def __init__(self, source=None, dest=None):
    Model.__init__(self)
    self._source = source
    self._dest = dest
  @property
  def source(self):
    return(self._source)
  @source.setter
  def source(self, value):
    if (value is not self._source):
      self._source = value
      self.on_change()
  @property
  def dest(self):
    return(self._dest)
  @dest.setter
  def dest(self, value):
    if (value is not self._dest):
      self._dest = value
      self.on_change()
  # connection serialization
  def serialize(self):
    return({ 
      'source': self.source,
      'dest': self.dest
    })
serializable.add(Connection)

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
