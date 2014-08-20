import time
import pypm
import re

from gi.repository import GLib, GObject

import core
from ..common import observable
from ..models import doc

# acts as a base class for MIDI input device adapters
class OutputAdapter(core.DeviceAdapter):
  def __init__(self, device):
    core.DeviceAdapter.__init__(self, device)
  # determine whether input is available from the named device
  def is_available(self):
    return((self.is_plugged) and 
           (self.is_output_available))
  # handle messages from the device
  def send_message(self, message, message_time):
    if (not self.device): return
    self.device.send(message, max(0.0, message_time - self.time))
serializable.add(OutputAdapter)

# a list of all available output devices
class OutputList(core.DeviceAdapterList):
  def __init__(self):
    core.DeviceAdapterList.__init__(self, adapter_class=OutputAdapter)
  def include_device(self, device):
    if (not device): return(False)
    if (device.name in ('Timer', 'Announce', 'Notify')): return(False)
    # we probably don't need the JACK interconnection client
    if (device.name.startswith('Midi Through')): return(False)
    # don't show LinuxSampler itself because we expose its instruments instead
    if (device.name.startswith('LinuxSampler')): return(False)
    return(device.is_output)
  
