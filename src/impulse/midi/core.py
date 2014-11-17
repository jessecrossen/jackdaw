import time
import jackpatch
import re
import yaml

from PySide.QtCore import *

from ..common import observable, serializable
from ..models import unit

# acts as a base class for MIDI device adapters
class DeviceAdapter(unit.Source, unit.Sink, observable.Object):
  def __init__(self, device_name):
    observable.Object.__init__(self)
    unit.Source.__init__(self)
    unit.Sink.__init__(self)
    self._source_type = 'midi'
    self._sink_type = 'midi'
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
      r'^(.*?)([Pp]ort|[Mm][Ii][Dd][Ii]|[0-9:#]+|[TtRr][Xx]|\.|\s+)*$', 
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
      self._source_port = self._device if self.has_output else None
      self._sink_port = self._device if self.has_input else None
      self.on_change()
  # return whether the device is currently plugged in to the system
  @property
  def is_plugged(self):
    return(self.device is not None)
  # return whether input/output ports are available for the device
  @property
  def has_input(self):
    if (not self.device): return(False)
    return((self.device.flags & jackpatch.JackPortIsInput) != 0)
  @property
  def has_output(self):
    if (not self.device): return(False)
    return((self.device.flags & jackpatch.JackPortIsOutput) != 0)
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
    # map devices by name
    self._name_map = dict()
    observable.List.__init__(self, adapters)
    # make a client connection to jack
    self._client = jackpatch.Client('jackdaw-devices')
    # scan for devices on a regular basis
    self.startTimer(1000)
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
  # respond to timer events by scanning for devices
  def timerEvent(self, event):
    self.scan()
  # scan for changes to the set of plugged in devices
  def scan(self):
    not_found = set(self._name_map.keys())
    # make sure all plugged-in devices have adapters
    devices = self._client.get_ports(type_pattern='.*midi.*')
    for device in devices:
      name = device.name
      # ignore ports created by this application
      if (name.startswith('jackdaw')): continue
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
    return({ 
      'adapters': list(self)
    })
serializable.add(DeviceAdapterList)

# handles input from MIDI devices
class InputHandler(observable.Object):
  def __init__(self, port, target):
    observable.Object.__init__(self)
    # store the source port and the target to send data to
    self._port = port
    self._target = target
    # add an idle timer to check for input
    self._timer = QTimer()
    self._timer.setInterval(0)
    self._timer.timeout.connect(self.receive)
    self._timer.start()
  @property
  def port(self):
    return(self._port)
  @property
  def target(self):
    return(self._target)
  # check for input
  def receive(self):
    while (True):
      result = self._port.receive()
      if (result is None): break
      (data, time) = result
      self.handle_message(data, time)
  # handle input, reimplement to pass data to the target
  def handle_message(data, time):
    pass