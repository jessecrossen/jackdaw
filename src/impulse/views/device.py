import math
import cairo

from gi.repository import Gtk, Gdk

import geom
from core import DrawableView, LayoutView, ViewManager, ListLayout

# lay out a list of devices
class DeviceLayout(ListLayout):
  def __init__(self, devices):
    ListLayout.__init__(self, devices)
    self.spacing = 4
  def size_of_item(self, device):
    return(len(device.name) * 10)

# show a single device
class DeviceView(LayoutView):
  def __init__(self, device):
    LayoutView.__init__(self, device)
    self.label = Gtk.Label()
    self.label.set_angle(90)
    self.label.set_alignment(0.5, 0.5)
    self.add(self.label)
  @property
  def device(self):
    return(self._model)
  def layout(self, width, height):
    self.label.size_allocate(geom.Rectangle(0, 0, width, height))
    self.label.set_text(self.device.name)

# show a vertical list of devices
class DeviceListView(LayoutView):
  def __init__(self, devices, device_layout):
    LayoutView.__init__(self, devices)
    self.device_layout = device_layout
    if (self.device_layout is None):
      self.device_layout = DeviceLayout(self.devices)
  @property
  def devices(self):
    return(self._model)
  def layout(self, width, height):
    views = self.allocate_views_for_models(
      self.devices, lambda d: DeviceView(d))
    for view in views:
      r = geom.Rectangle(
        0, self.device_layout.position_of_item(view.device),
        width, self.device_layout.size_of_item(view.device))
      view.size_allocate(r)
      
# show an interface to route between two lists
class PatchBayView(DrawableView):
  def __init__(self, patch_bay, left_list, left_layout, right_list, right_layout):
    DrawableView.__init__(self, patch_bay)
    self.left_list = left_list
    self.left_layout = left_layout
    self.right_list = right_list
    self.right_layout = right_layout
    self.left_list.add_observer(self.on_change)
    self.right_list.add_observer(self.on_change)
  @property
  def patch_bay(self):
    return(self._model)
  def redraw(self, cr, width, height):
    #TODO
    pass
  
    
    
