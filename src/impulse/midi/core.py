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
  # connect the device automatically based on its name
  def connect(self):
    self.connect_by_name(self.name)
  # connect to the first device with the given name or name fragment
  def connect_by_name(self, name):
    in_port = self.get_port_by_name(self._in, name)
    out_port = self.get_port_by_name(self._out, name)
    if (in_port is not None):
      self._in.open_port(in_port)
    else:
      print('Failed to connect input for the device named %s.' % (name))
    if (out_port is not None):
      self._out.open_port(out_port)
    else:
      print('Failed to connect output for the device named %s.' % (name))
    if ((in_port is not None) or (out_port is not None)):
      self.on_connect()
  # disconnect from inputs and outputs
  def disconnect(self):
    self.on_disconnect()
    del self._in
    del self._out
    self._in = rtmidi.MidiIn()
    self._out = rtmidi.MidiOut()
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
