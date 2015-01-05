import math

from PySide.QtCore import *
from PySide.QtGui import *

import midi
import view
import unit_view

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

# make a unit view containing a list of input devices
class DeviceListUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._content = DeviceListView(
      devices=self.unit.devices, 
      require_input=self.unit.require_input,
      require_output=self.unit.require_output)
    self._content.setParentItem(self)
    # add inputs and outputs for the devices
    self._input_layout = unit_view.InputListLayout(self, self.unit.devices, 
                                            self.input_view_for_device)
    self._output_layout = unit_view.OutputListLayout(self, self.unit.devices, 
                                            self.output_view_for_device)
  def input_view_for_device(self, device):
    if (not device.has_input):
      if (self.unit.require_input):
        return(None)
      # if the unit has no input, return a placeholder
      return(view.ModelView(device))
    if ((self.unit.require_output) and (not device.has_output)):
      return(None)
    return(unit_view.UnitInputView(device))
  def output_view_for_device(self, device):
    if (not device.has_output):
      if (self.unit.require_output):
        return(None)
      # if the unit has no output, return a placeholder
      return(view.ModelView(device))
    if ((self.unit.require_input) and (not device.has_input)):
      return(None)
    return(unit_view.UnitOutputView(device))
  def layout(self):
    size = self._content.minimumSizeHint()
    self._content.setRect(QRectF(0, 0, size.width(), size.height()))
    unit_view.UnitView.layout(self)
# register the view for placement on the workspace
unit_view.UnitView.register_unit_view(
  midi.DeviceListUnit, DeviceListUnitView)

# make a view that displays incoming MIDI messages
class MidiMonitorUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._input_layout = unit_view.InputListLayout(self, (self.unit,), 
                          lambda t: unit_view.UnitInputView(t))
    self.allow_delete = True
    self.allow_resize_width = True
    self.allow_resize_height = True
    text = QGraphicsTextItem(self)
    text.setPos(QPointF(0.0, 0.0))
    font = QFont('monospace')
    font.setStyleHint(QFont.Monospace)
    text.setFont(font)
    self._content = text
    self._metrics = QFontMetrics(font)
    self.unit.add_observer(self.render)
  def destroy(self):
    self.unit.remove_observer(self.render)
    unit_view.UnitView.destroy(self)
  # allow the area to expand independent of the text view
  def content_size(self):
    s = unit_view.UnitView.content_size(self)
    s.setWidth(max(s.width(), self.unit.width))
    s.setHeight(max(s.height(), self.unit.height))
    return(s)
  # show a textual represenation of MIDI events
  def render(self):
    messages = self.unit.messages
    lines = list()
    line_height = self._metrics.lineSpacing()
    max_height = self.unit.height
    style = self.unit.style
    show_time = self.unit.show_time
    for (data, time) in reversed(messages):
      if (style == 'decimal'):
        line = ', '.join(map(str, data))+' '
      elif (style == 'binary'):
        line = ' '.join(map('{0:08b}'.format, data))+' '
      else:
        line = ('%02X ' * len(data)) % tuple(data)
      if (show_time):
        line += '(%0.3f)' % time
      lines.append(line)
      if (len(lines) * line_height >= max_height): break
    self._content.setPlainText('\n'.join(reversed(lines)))
    self.layout()
unit_view.UnitView.register_unit_view(
  midi.MidiMonitorUnit, MidiMonitorUnitView)