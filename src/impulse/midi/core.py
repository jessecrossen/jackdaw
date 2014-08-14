import time
import alsamidi
import re

from gi.repository import GLib, GObject

from ..common import observable

# acts as a base class for MIDI device adapters
class DeviceAdapter(observable.Object):
  def __init__(self, device):
    observable.Object.__init__(self)
    self.device = device
    self._is_plugged = False
    self._is_connected = False
  # return whether the device is currently plugged in to the system
  @property
  def is_plugged(self):
    return(self._is_plugged)
  @is_plugged.setter
  def is_plugged(self, value):
    if (value != self._is_plugged):
      self._is_plugged = value
      self.on_change()
  # return the complete device name
  @property
  def name(self):
    if (not self.device): return('')
    return(self.device.name)
  # return a shorter version of the device name
  @property
  def short_name(self):
    m = re.match('\\S*', self.name)
    return(m.group(0))
  # return whether the device is connected
  @property
  def is_connected(self):
    if (not self.device): return(False)
    return((self._is_connected) and (self.device.is_connected))
  # return whether input/output ports are available for the device
  @property
  def is_input_available(self):
    if (not self.device): return(False)
    return(self.device.is_input)
  @property
  def is_output_available(self):
    if (not self.device): return(False)
    return(self.device.is_output)
  # connect the device
  def connect(self):
    if ((self.device) and (not self._is_connected)):
      self.device.connect()
      self.on_connect()
      self._is_connected = True
  def disconnect(self):
    if ((self.device) and (self._is_connected)):
      # TODO: device disconnection
      pass
      self.on_disconnect()
      self._is_connected = False
  # override these to perform actions on connect/disconnect
  def on_connect(self):
    pass
  def on_disconnect(self):
    pass

# keep a core list of devices keyed by name and location so we can 
#  scan hotplugged devices and not replace connected ones
class DevicePoolSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self._plugged = dict()
    self._unplugged = dict()
  # return plugged-in devices
  @property
  def plugged(self):
    return(self._plugged.values())
  @property
  def unplugged(self):
    return(self._unplugged.values())
  # scan for new devices
  def scan(self):
    devices = alsamidi.get_devices()
    plugged = dict()
    unplugged = self._plugged.copy()
    for device in devices:
      key = (device.name, device.client, device.port)
      # existing device
      if (key in self._plugged):
        del unplugged[key]
      # unplugged device that got plugged back in
      elif (key in self._unplugged):
        plugged[key] = device
        del self._uplugged[key]
      # newly plugged-in device
      else:
        plugged[key] = device
    if (len(plugged) > 0):
      self._plugged.update(plugged)
      self.on_change()
    if (len(unplugged) > 0):
      self._unplugged.update(unplugged)
      self.on_change()
# make a shared device pool and periodically scan for 
#  plugged/unplugged devices
DevicePool = DevicePoolSingleton()
DevicePool.scan()
GLib.timeout_add(5000, DevicePool.scan)      

# keep a list of device adapters matching a certain filter
class DeviceAdapterList(observable.List):
  def __init__(self, adapter_class):
    observable.List.__init__(self)
    self.adapter_class = adapter_class
    self._included = set()
    DevicePool.add_observer(self.on_pool_change)
    self.on_pool_change()
  # determine whether to include the given device in the list
  def include_device(self, device):
    return(False)
  # filter devices for inclusion in the list
  def on_pool_change(self):
    plugged = set(DevicePool.plugged)
    for device in plugged:
      if (self.include_device(device)):
        if (device not in self._included):
          self._included.add(device)
          self.append(self.adapter_class(device))
    for adapter in self:
      adapter.is_plugged = (adapter.device in plugged)
