import math

from PySide.QtCore import *
from PySide.QtGui import *

import core

# make a view that displays a list of midi devices
class DeviceListView(core.ModelView):
  def __init__(self, devices, require_input=False, require_output=False, 
                     parent=None):
    core.ModelView.__init__(self, model=devices, parent=parent)
    self.require_input = require_input
    self.require_output = require_output
    self.device_layout = core.VBoxLayout(self, devices, self.view_for_device)
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
class DeviceView(core.ModelView):
  def __init__(self, device, parent=None):
    core.ModelView.__init__(self, model=device, parent=parent)
    self.name_proxy = None
  @property
  def device(self):
    return(self._model)
  # get the minimum size needed to display the device
  def minimumSizeHint(self):
    if (self.name_proxy):
      name_view = self.name_proxy.widget()
      return(name_view.minimumSizeHint())
    return(QSizeF(0, 0))
  # provide a height for layout in the parent
  def rect(self):
    r = core.ModelView.rect(self)
    r.setHeight(self.minimumSizeHint().height())
    return(r)
  def layout(self):
    if ((self.scene()) and (not self.name_proxy)):
      name_view = core.NameLabel(self.device)
      self.name_proxy = self.scene().addWidget(name_view)
      self.name_proxy.setParentItem(self)
    if (self.name_proxy):
      r = self.boundingRect()
      name_view = self.name_proxy.widget()
      name_view.setFixedWidth(r.width())
      self.name_proxy.setPos(QPointF(0.0, 0.0))
    # fade the view if the device is unplugged
    self.setOpacity(1.0 if self.device.is_plugged else 0.5)
  def paint(self, qp, options, widget):
    r = self.boundingRect()
    qp.setPen(Qt.NoPen)
    color = self.palette.color(QPalette.Normal, QPalette.Base)
    qp.setBrush(QBrush(color))
    qp.drawRoundedRect(r, 4.0, 4.0)
