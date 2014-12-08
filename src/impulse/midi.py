import time
import jackpatch
import re
import yaml

from PySide.QtCore import QTimer

import observable
import serializable
import unit

# handles a placeholder and adapter for a JACK midi device
class DeviceAdapter(unit.Source, unit.Sink, observable.Object):
  def __init__(self, device_name, device_flags=0):
    observable.Object.__init__(self)
    unit.Source.__init__(self)
    unit.Sink.__init__(self)
    self._source_type = 'midi'
    self._sink_type = 'midi'
    self._device_name = device_name
    self._device_flags = device_flags
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
      self._device_flags = 0
      if (device is not None):
        self._device_flags = self._device.flags
      self._source_port = self._device if self.has_output else None
      self._sink_port = self._device if self.has_input else None
      self.on_change()
  # return whether the device is currently plugged in to the system
  @property
  def is_plugged(self):
    return(self.device is not None)
  # return all device flags
  @property
  def device_flags(self):
    if (self.device is not None): return(self.device.flags)
    return(self._device_flags)
  # return whether input/output ports are available for the device
  @property
  def has_input(self):
    return((self.device_flags & jackpatch.JackPortIsInput) != 0)
  @property
  def has_output(self):
    return((self.device_flags & jackpatch.JackPortIsOutput) != 0)
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
  # adapter serialization
  def serialize(self):
    return({ 
      'device_name': self._device_name,
      'device_flags': self._device_flags
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

# make a unit that represents a list of MIDI devices
class DeviceListUnit(unit.Unit):
  def __init__(self, devices, require_input=False, require_output=False, 
               *args, **kwargs):
    unit.Unit.__init__(self, *args, **kwargs)
    self.devices = devices
    self.require_input = require_input
    self.require_output = require_output
    self.devices.add_observer(self.on_change)
  def serialize(self):
    obj = unit.Unit.serialize(self)
    obj['devices'] = self.devices
    obj['require_input'] = self.require_input
    obj['require_output'] = self.require_output
    return(obj)
serializable.add(DeviceListUnit)

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
    # wrap the target in a change block so each midi event doesn't waste a lot
    #  of time causing cascading changes
    target_and_refs = (self._target,)
    try:
      target_and_refs += self._target.model_refs
    except AttributeError: pass
    for model in target_and_refs:
      try:
        model.begin_change_block()
      except AttributeError: pass
    while (True):
      result = self._port.receive()
      if (result is None): break
      (data, time) = result
      self.handle_message(data, time)
    for model in target_and_refs:
      try:
        model.end_change_block()
      except AttributeError: pass
  # handle input, reimplement to pass data to the target
  def handle_message(data, time):
    pass