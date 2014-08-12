import time
import pypm
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
class OutputDeviceList(core.DeviceList):
  def __init__(self, devices=()):
    core.DeviceList.__init__(self, devices, device_class=OutputDevice)
    GLib.timeout_add(5000, self.scan)
  def filter_device(self, name, is_input, is_output):
    return(is_output)

