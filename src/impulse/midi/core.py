import time
import alsamidi
import re
import yaml

from ..common import observable, serializable

# device serialization
def device_representer(dumper, device):
  return(dumper.represent_mapping(u'!device', { 
    'name': device.name,
    'client': device.client,
    'port': device.port
  }))
def device_constructor(loader, node):
  kwargs = loader.construct_mapping(node, deep=True)
  return(alsamidi.Device(**kwargs))
yaml.add_representer(alsamidi.Device, device_representer)
yaml.add_constructor('!device', device_constructor)

# acts as a base class for MIDI device adapters
class DeviceAdapter(observable.Object):
  def __init__(self, device):
    observable.Object.__init__(self)
    self.device = device
    self._is_plugged = False
    self._is_connected = False
    self._base_time = 0.0
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
    m = re.match(
      '^(.*?)(\\s+([Pp]ort|[Mm][Ii][Dd][Ii]|[0-9:]+|\\s+)*)?$', self.name)
    return(m.group(1))
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
    if ((self.device) and 
        ((not self._is_connected) or (not self.device.is_connected))):
      self.device.connect()
      self.on_connect()
      self._is_connected = True
  def disconnect(self):
    if ((self.device) and 
        ((self._is_connected) or (self.device.is_connected))):
      self.device.disconnect()
      self.on_disconnect()
      self._is_connected = False
  # override these to perform actions on connect/disconnect
  def on_connect(self):
    pass
  def on_disconnect(self):
    pass
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
      'device': self.device
    })
serializable.add(DeviceAdapter)

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
    changed = False
    devices = alsamidi.get_devices()
    not_found = dict(self._plugged)
    for device in devices:
      key = (device.client, device.port)
      # existing device
      if (key in self._plugged):
        del not_found[key]
        # update the device's name in case it changed while plugged in
        if (self._plugged[key].name != device.name):
          self._plugged[key].name = device.name
          changed = True
      # unplugged device that got plugged back in
      elif (key in self._unplugged):
        # if the name has changed while unplugged, 
        #  it's probably not the same device
        if (self._unplugged[key].name != device.name): continue
        # otherwise transfer the device to the plugged-in pool
        self._plugged[key] = self._unplugged[key]
        del self._unplugged[key]
        changed = True
      # newly plugged-in device
      else:
        self._plugged[key] = device
        changed = True
    # see if any devices were unplugged
    for (key, device) in not_found.iteritems():
      self._unplugged[key] = self._plugged[key]
      del self._plugged[key]
      changed = True
    if (changed):
      self.on_change()
    return(True)
# make a shared device pool and periodically scan for 
#  plugged/unplugged devices
DevicePool = DevicePoolSingleton()
DevicePool.scan()
GLib.timeout_add(2000, DevicePool.scan)      

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
