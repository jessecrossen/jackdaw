import time
import rtmidi
import re

from gi.repository import GLib, GObject

import core
from ..common import observable
from ..models import doc

# acts as a base class for MIDI input device adapters
class OutputDevice(core.Device):
  def __init__(self, name):
    core.Device.__init__(self, name)
  # determine whether input is available from the named device
  def is_available(self):
    return((self.is_connected) or 
           (self.is_output_available))

# a list of all available output devices
class OutputDeviceList(observable.List):
  def __init__(self):
    observable.List.__init__(self)
    self._names_in_list = set()
    self.update()
    GLib.timeout_add(5000, self.update)
  # update the list from available ports
  def update(self):
    connection = rtmidi.MidiOut()
    port_count = connection.get_port_count()
    for port in range(0, port_count):
      name = connection.get_port_name(port)
      # ignore RtMidi devices, which are likely ours
      if (name.startswith('RtMidi')): continue
      m = re.search(r'^(.*?)(\s[0-9:]+)?$', name)
      name = m.group(1)
      # strip off the numbers
      if (name not in self._names_in_list):
        self._names_in_list.add(name)
        self.append(OutputDevice(name))
    return(True)
