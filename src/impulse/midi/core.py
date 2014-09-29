import time
import alsamidi
import re
import yaml

from PySide.QtCore import *

from ..common import observable, serializable

# acts as a base class for MIDI device adapters
class DeviceAdapter(observable.Object):
  def __init__(self, device_name):
    observable.Object.__init__(self)
    self._device_name = device_name
    self._device = None
    self._base_time = 0.0
    # default to a short version of the device name
    self._name = ''
  # get the name of the device this adapter was created for
  @property
  def device_name(self):
    return(self._device_name)
  # get a shortened version of the device name
  @property
  def short_device_name(self):
    m = re.match(
      '^(.*?)(\\s+([Pp]ort|[Mm][Ii][Dd][Ii]|[0-9:]+|\\s+)*)?$', 
      self.device_name)
    return(m.group(1))
  # get and set the current backing device
  @property
  def device(self):
    return(self._device)
  @device.setter
  def device(self, device):
    if (device is not self._device):
      self._device = device
      self.on_change()
  # return whether the device is currently plugged in to the system
  @property
  def is_plugged(self):
    return(self.device is not None)
  # return whether the device is connected
  @property
  def is_connected(self):
    if (not self.device): return(False)
    return(self.device.is_connected)
  # return whether input/output ports are available for the device
  @property
  def has_input(self):
    if (not self.device): return(False)
    return(self.device.is_input)
  @property
  def has_output(self):
    if (not self.device): return(False)
    return(self.device.is_output)
  # return the complete device name
  @property
  def name(self):
    if (len(self._name) > 0):
      return(self._name)
    return(self.short_device_name)
  @name.setter
  def name(self, name):
    if (name != self._name):
      self._name = name
      self.on_change()
  # get the amount of time elapsed since the time origin
  @property
  def time(self):
    if (not self.device): return(0.0)
    return(self.device.get_time() - self._base_time)
  # reset the time origin to the given value, such that subsequent
  #  messages have a time relative to it
  @time.setter
  def time(self, value):
    if (self.device):
      self._base_time = self.device.get_time() - value
    else:
      self._base_time = - value
  # adapter serialization
  def serialize(self):
    return({ 
      'device_name': self._device_name
    })
serializable.add(DeviceAdapter)

# make a class to manage a list of adapters
class DeviceAdapterList(observable.List):
  def __init__(self, adapters=()):
    observable.List.__init__(self, adapters)
    # scan periodically for devices being plugged and unplugged
    self.scan_timer = QTimer()
    self.scan_timer.timeout.connect(self.scan)
    self.scan_timer.start(1000)
    # map devices by name
    self._name_map = dict()
  # get an adapter for the device with the given name
  def adapter_named(self, name):
    if (name not in self._name_map):
      self.append(DeviceAdapter(device_name=name))
    return(self._name_map[name])
  # keep items mapped by name
  def _add_item(self, item):
    self._name_map[item.device_name] = item
    observable.List._add_item(self, item)
  def _remove_item(self, item):
    del self._name_map[item.device_name]
    observable.List._remove_item(self, item)
  # scan for changes to the set of plugged in devices
  def scan(self):
    not_found = set(self._name_map.keys())
    # make sure all plugged-in devices have adapters
    devices = alsamidi.get_devices()
    for device in devices:
      name = device.name
      if (name in not_found):
        not_found.remove(name)
      adapter = self.adapter_named(name)
      if (adapter.device is None):
        adapter.device = device
    # disconnect missing devices from their adapters
    for name in not_found:
      adapter = self.adapter_named(name)
      adapter.device = None
  # adapter list serialization
  def serialize(self):
    names = list()
    for adapter in self:
      names
    return({ 
      'adapters': list(self)
    })
serializable.add(DeviceAdapterList)


