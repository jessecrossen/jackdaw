import math
import cairo

from gi.repository import Gtk, Gdk

import geom
import symbols
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
    self.make_interactive()
    self._drag_source_list = None
    self._drag_source = None
    self._drag_target = None
    self._over_connection = None
    self._over_item = None
    self._over_list = None
    self._over_dir = 0
    self._connection_points = dict()
    self.left_list = left_list
    self.left_layout = left_layout
    self.right_list = right_list
    self.right_layout = right_layout
    self.left_list.add_observer(self.on_change)
    self.right_list.add_observer(self.on_change)
    self.left_area = geom.Rectangle()
    self.right_area = geom.Rectangle()
    # map drawn connection lines
    self._lines = [ ]
    # use special cursors in the active areas
    self.cursor_areas[self.left_area] = Gdk.Cursor(
      Gdk.CursorType.SB_RIGHT_ARROW)
    self.cursor_areas[self.right_area] = Gdk.Cursor(
      Gdk.CursorType.SB_LEFT_ARROW)
  @property
  def patch_bay(self):
    return(self._model)
  def redraw(self, cr, width, height):
    # get the color to draw with
    style = self.get_style_context()
    fg = style.get_color(self.get_state_flags())
    # add the connection being dragged, if any
    connections = self.patch_bay.connections
    if (self._drag_source_list is self.left_list):
      connections.add((self._drag_source, self._drag_target))
    elif (self._drag_source_list is self.right_list):
      connections.add((self._drag_target, self._drag_source))
    # size the active areas for starting a drag
    self._left_x = 2 * symbols.BRACKET_WIDTH
    self._right_x = width - symbols.RADIUS - 1
    self.left_area.width = self._left_x + (4 * symbols.RADIUS)
    if (len(self.left_list) > 0):
      self.left_area.height = (
        self.left_layout.position_of_item(self.left_list[-1]) +
        self.left_layout.size_of_item(self.left_list[-1]))
    else:
      self.left_area.height = 0
    self.right_area.x = self._right_x - (4 * symbols.RADIUS)
    self.right_area.width = width - self.right_area.x
    if (len(self.right_list) > 0):
      self.right_area.height = (
        self.right_layout.position_of_item(self.right_list[-1]) +
        self.right_layout.size_of_item(self.right_list[-1]))
    else:
      self.right_area.height = 0
    # get the y coordinate for an item from the given layout
    def y_of_item(item, layout):
      return(layout.position_of_item(item) + 
             (layout.size_of_item(item) / 2))
    # get lines between all connections in the patch bay
    lines = [ ]
    unused_left = set(self.left_list)
    unused_right = set(self.right_list)
    for connection in connections:
      style = '*~*'
      (left_item, right_item) = connection
      if (isinstance(left_item, geom.Point)):
        lx = left_item.x
        ly = left_item.y
        style = '<'+style[1:]
      elif (left_item in self.left_list):
        lx = self._left_x
        ly = y_of_item(left_item, self.left_layout)
        if (left_item in unused_left):
          unused_left.remove(left_item)
      else:
        continue
      if (isinstance(right_item, geom.Point)):
        rx = right_item.x
        ry = right_item.y
        style = style[0:-1]+'>'
      elif (right_item in self.right_list):
        rx = self._right_x
        ry = y_of_item(right_item, self.right_layout)
        if (right_item in unused_right):
          unused_right.remove(right_item)
      else:
        continue
      lp = geom.Point(lx, ly)
      rp = geom.Point(rx, ry)
      lines.append((lp, rp, style, connection))
    # add endpoints at unconnected items
    for item in unused_left:
      lines.append((geom.Point(
        self._left_x, y_of_item(item, self.left_layout)), None, 
        'o', None))
    for item in unused_right:
      lines.append((None, geom.Point(
        self._right_x, y_of_item(item, self.right_layout)), 
        'o', None))
    # index connections by position
    lefts = dict()
    rights = dict()
    for (lp, rp, s, c) in lines:
      if (lp):
        lk = (lp.x, lp.y)
        if (lk not in lefts):
          lefts[lk] = [ ]
        lefts[lk].append((lp, rp))
      if (rp):
        rk = (rp.x, rp.y)
        if (rk not in rights):
          rights[rk] = [ ]
        rights[rk].append((rp, lp))
    # sort connections to minimize crossing    
    def sort_key(p):
      if (p[1] is None): return(1000000)
      else: return(p[1].y - p[0].y)
    for (lk, dirs) in lefts.iteritems():
      dirs.sort(key=sort_key)
    for (rk, dirs) in rights.iteritems():
      dirs.sort(key=sort_key)
    # interconnect connections on each side
    groups = lefts.values()
    groups.extend(rights.values())
    for dirs in groups:
      last = None
      for p in dirs:
        if (last):
          lines.append((last[0], p[0], '-', None))
        last = p
    # spread connections out so each has its own endpoint
    #  but there is always one in the center position
    def spread(num, i):
      step = (symbols.RADIUS * 2) + 4
      return((i - math.floor((num - 1) / 2.0)) * step)
    for (lk, dirs) in lefts.iteritems():
      for i in range(0, len(dirs)):
        dirs[i][0].y = lk[1] + spread(len(dirs), i)
    for (rk, dirs) in rights.iteritems():
      for i in range(0, len(dirs)):
        dirs[i][0].y = rk[1] + spread(len(dirs), i)
    # add a prospective connection when dragging would make one
    if ((self._over_item) and (not self._over_connection) and
        (self._over_item is not self._drag_source)):
      if ((self._over_list is self.left_list) and 
          (self._over_item not in unused_left)):
        p2 = geom.Point(
          self._left_x, y_of_item(self._over_item, self.left_layout))
        num = len(lefts[(p2.x, p2.y)])
        if (self._over_dir < 0):
          p1 = geom.Point(p2.x, p2.y + spread(num, 0))
          p2.y += spread(num, -1)
        else:
          p1 = geom.Point(p2.x, p2.y + spread(num, num - 1))
          p2.y += spread(num, num)
        symbols.draw_path(cr, (p1, p2), '-o')
      elif ((self._over_list is self.right_list) and 
            (self._over_item not in unused_right)):
        p2 = geom.Point(
          self._right_x, y_of_item(self._over_item, self.right_layout))
        num = len(rights[(p2.x, p2.y)])
        if (self._over_dir < 0):
          p1 = geom.Point(p2.x, p2.y + spread(num, 0))
          p2.y += spread(num, -1)
        else:
          p1 = geom.Point(p2.x, p2.y + spread(num, num - 1))
          p2.y += spread(num, num)
        symbols.draw_path(cr, (p1, p2), '-o')
    # draw stubs for interconnecting with views to the left and right
    cr.set_line_width(2)
    for item in self.left_list:
      y = y_of_item(item, self.left_layout)
      symbols.draw_path(cr, 
        (geom.Point(symbols.BRACKET_WIDTH, y), geom.Point(self._left_x, y)), '}-')
    for item in self.right_list:
      y = y_of_item(item, self.right_layout)
      symbols.draw_line(cr, 
        geom.Point(self._right_x, y), geom.Point(width, y), '-')
    # draw connections
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
    for (lp, rp, s, c) in lines:
      # show an X when the cursor is over a connection
      if ((c) and (self._over_connection is c)):
        if (self._over_item is c[0]):
          s = 'x'+s[1:]
        else:
          s = s[:-1]+'x'
      symbols.draw_connection(cr, lp, rp, s)
    # store connection positions for mouseover effects
    self._lines = lines
  
  # track the cursor
  def update_cursor(self, x, y, state):
    over_connection = None
    over_item = None
    over_list = None
    over_dir = 0
    if (self.left_area.contains(x, y)):
      over_list = self.left_list
      for (lp, rp, s, c) in self._lines:
        if ((lp) and (rp) and (c) and 
            (abs(y - lp.y) <= symbols.RADIUS + 2)):
          over_connection = c
          over_item = c[0]
          break
      over_item = self.left_layout.item_at_position(y)
      if (y < self.left_layout.center_of_item(over_item)):
        over_dir = -1
      else:
        over_dir = 1
    elif (self.right_area.contains(x, y)):
      over_list = self.right_list
      for (lp, rp, s, c) in self._lines:
        if ((lp) and (rp) and (c) and
            (abs(y - rp.y) <= symbols.RADIUS + 1)):
          over_connection = c
          over_item = c[1]
          break
      over_item = self.right_layout.item_at_position(y)
      if (y < self.right_layout.center_of_item(over_item)):
        over_dir = -1
      else:
        over_dir = 1
    if ((over_connection != self._over_connection) or
        (over_item != self._over_item) or
        (over_list != self._over_list) or
        (over_dir != self._over_dir)):
      self._over_connection = over_connection
      self._over_item = over_item
      self._over_list = over_list
      self._over_dir = over_dir
      self.on_change()
  # enable dragging to connect/disconnect
  def start_drag(self, x, y, state):
    self._drag_source = None
    if (self._over_connection):
      c = self._over_connection
      self.patch_bay.disconnect(c[0], c[1])
      if (self._over_item is c[0]):
        self._drag_source = c[1]
        self._drag_source_list = self.right_list
      else:
        self._drag_source = c[0]
        self._drag_source_list = self.left_list
    elif (self.left_area.contains(x, y)):
      self._drag_source_list = self.left_list
      self._drag_source = self.left_layout.item_at_position(y)
    elif (self.right_area.contains(x, y)):
      self._drag_source_list = self.right_list
      self._drag_source = self.right_layout.item_at_position(y)
    if (self._drag_source is not None):
      self._drag_target = geom.Point(x, y)
      return(True)
    else:
      self._drag_source_list = None
      return(False)
  # update the drag position
  def on_drag(self, dx, dy, state):
    (win, x, y, state) = self.get_window().get_pointer()
    item = None
    if ((self._drag_source_list is self.left_list) and
        (self.right_area.contains(x, y))):
      item = self.right_layout.item_at_position(y)
      # if there's already a connection, don't snap into it because
      #  it looks like the dragged connection is disappearing
      if ((self._drag_source, item) in self.patch_bay.connections):
        item = None
    if ((self._drag_source_list is self.right_list) and
        (self.left_area.contains(x, y))):
      item = self.left_layout.item_at_position(y)
      if ((item, self._drag_source) in self.patch_bay.connections):
        item = None
    if (item is not None):
      self._drag_target = item
    else:
      self._drag_target = geom.Point(x, y)
    self.on_change()
    
  def on_drop(self):
    if ((self._drag_source_list is self.left_list) and
        (not isinstance(self._drag_target, geom.Point))):
      self.patch_bay.connect(self._drag_source, self._drag_target)
    if ((self._drag_source_list is self.right_list) and
        (not isinstance(self._drag_target, geom.Point))):
      self.patch_bay.connect(self._drag_target, self._drag_source)
    self._drag_source_list = None
    self._drag_source = None
    self._drag_target = None
    self._over_connection = None
    self._over_item = None
    self._over_list = None
    self.on_change()
