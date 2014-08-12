import time
import pypm
import re

from gi.repository import GLib, GObject

from ..common import observable

# acts as a base class for MIDI device adapters
class Device(object):
  def __init__(self, name):
    self.name = name
    self._in = None
    self._out = None
  # return a shorter version of the device name
  @property
  def short_name(self):
    m = re.match('\\S+', self.name)
    return(m.group(0))
  # return whether the device is connected
  @property
  def is_connected(self):
    return(self._in or self._out)
  # return whether input/output ports are available for the device
  @property
  def is_input_available(self):
    return(self.get_port_by_name(self._in, self.name) is not None)
  @property
  def is_output_available(self):
    return(self.get_port_by_name(self._out, self.name) is not None)
  # connect the device automatically based on its name
  def connect(self):
    if (self.is_connected): return
    self.connect_by_name(self.name)
  # connect to the first device with the given name
  def connect_by_name(self, name):
    for port in range(0, pypm.CountDevices()):
      (interface, device_name, is_input, is_output, opened) = (
        pypm.GetDeviceInfo(port))
      if (device_name == name):
        if (is_input):
          self._in = pypm.Input(port)
        if (is_output):
          self._out = pypm.Output(port, 0)
    if (self.is_connected):
      self.on_connect()
  # disconnect from inputs and outputs
  def disconnect(self):
    self.on_disconnect()
    if (self._in):
      del self._in
    if (self._out):
      del self._out
    self._in = None
    self._out = None
  # override these to perform actions on connect/disconnect
  def on_connect(self):
    pass
  def on_disconnect(self):
    pass

# lists devices
class DeviceList(observable.List):
  def __init__(self, devices, device_class):
    observable.List.__init__(self, devices)
    self.device_class = device_class
    self._bound_names = set()
    self.scan()
  # determine whether to include the given device in the list
  def filter_device(self, name, is_input, is_output):
    return(False)
  # scan for newly plugged-in devices
  def scan(self):
    for port in range(0, pypm.CountDevices()):
      (interface, device_name, is_input, is_output, opened) = (
        pypm.GetDeviceInfo(port))
      if ((device_name not in self._bound_names) and 
          (self.filter_device(device_name, is_input, is_output))):
        self._bound_names.add(device_name)
        self.append(self.device_class(device_name))
    
