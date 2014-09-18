from ..common import serializable
from core import Model, ModelList

# represent a device, which can be connected to other devices
class Device(Model):
  def __init__(self, name='Device', x=0, y=0):
    Model.__init__(self)
    self._name = name
    self._x = x
    self._y = y
  # get and set the name of the device
  @property
  def name(self):
    return(self._name)
  @name.setter
  def name(self, value):
    if (value != self._name):
      self._name = value
      self.on_change()
  # get and set the position of the device on the workspace
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
  # device serialization
  def serialize(self):
    return({ 
      'name': self.name,
      'x': self.x,
      'y': self.y
    })
serializable.add(Device)

# represent a list of devices
class DeviceList(ModelList):
  def __init__(self, devices=()):
    ModelList.__init__(self, devices)
  # track serialization
  def serialize(self):
    return({ 
      'devices': list(self)
    })
serializable.add(DeviceList)

# make a device that represents the track list of the document
class MultitrackDevice(Device):
  def __init__(self, tracks, view_scale, transport, *args, **kwargs):
    Device.__init__(self, *args, **kwargs)
    self.tracks = tracks
    self.transport = transport
    self.view_scale = view_scale
  def serialize(self):
    obj = Device.serialize(self)
    obj['tracks'] = self.tracks
    obj['transport'] = self.transport
    obj['view_scale'] = self.view_scale
    return(obj)
serializable.add(MultitrackDevice)
