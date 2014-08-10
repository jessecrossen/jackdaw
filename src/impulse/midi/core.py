import time
import rtmidi

from gi.repository import GLib, GObject

from ..common import observable

# acts as a base class for MIDI device adapters
class Device(object):
  def __init__(self, name):
    self.name = name
    self._in = rtmidi.MidiIn()
    self._out = rtmidi.MidiOut()
    self._input_connected = False
    self._output_connected = False
  # return whether the device is connected
  @property
  def is_connected(self):
    return(self._input_connected or self._output_connected)
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
  # connect to the first device with the given name or name fragment
  def connect_by_name(self, name):
    in_port = self.get_port_by_name(self._in, name)
    out_port = self.get_port_by_name(self._out, name)
    if (in_port is not None):
      self._in.open_port(in_port)
      self._input_connected = True
    if (out_port is not None):
      self._out.open_port(out_port)
      self._output_connected = True
  # disconnect from inputs and outputs
  def disconnect(self):
    self.on_disconnect()
    del self._in
    del self._out
    self._in = rtmidi.MidiIn()
    self._out = rtmidi.MidiOut()
    self._input_connected = False
    self._output_connected = False
  # get the port on the given input/output with the given name
  def get_port_by_name(self, connection, name):
    port_count = connection.get_port_count()
    for port in range(0, port_count):
      device_name = connection.get_port_name(port)
      if (name in device_name):
        return(port)
    return(None)
  # override these to perform actions on connect/disconnect
  def on_connect(self):
    pass
  def on_disconnect(self):
    pass
