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

# a list of all available output devices
class OutputList(core.DeviceAdapterList):
  def __init__(self):
    core.DeviceAdapterList.__init__(self, adapter_class=OutputAdapter)
  def include_device(self, device):
    return((device) and (device.is_output))

