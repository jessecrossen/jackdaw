import math

from PySide.QtCore import *
from PySide.QtGui import *

import view

# make a view that displays a list of midi devices
class DeviceListView(view.ModelView):
  def __init__(self, devices, require_input=False, require_output=False, 
                     parent=None):
    view.ModelView.__init__(self, model=devices, parent=parent)
    self.require_input = require_input
    self.require_output = require_output
    self.device_layout = view.VBoxLayout(self, devices, self.view_for_device)
    self.device_layout.spacing = 6.0
  def view_for_device(self, device):
    if ((self.require_input) and (not device.has_input)):
      return(None)
    if ((self.require_output) and (not device.has_output)):
      return(None)
    return(DeviceView(device))
  @property
  def devices(self):
    return(self._model)
  def minimumSizeHint(self):
    w = 120; h = 0
    for view in self.device_layout.views:
      s = view.minimumSizeHint()
      w = max(w, s.width())
      h += s.height() + self.device_layout.spacing
    return(QSizeF(w, h))
  def layout(self):
    self.device_layout.setRect(self.boundingRect())

# make a view that displays an input device
class DeviceView(view.NamedModelView):
  def __init__(self, device, parent=None):
    view.NamedModelView.__init__(self, model=device, parent=parent)
  @property
  def device(self):
    return(self._model)
  def layout(self):
    view.NamedModelView.layout(self)
    # fade the view if the device is unplugged
    self.setOpacity(1.0 if self.device.is_plugged else 0.5)
