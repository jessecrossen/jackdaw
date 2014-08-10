import math
import weakref

from gi.repository import Gtk, Gdk, GLib

from ..common import observable
import geom
import state

# make a singleton for handling things like selection state
class ViewManagerSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self.reset()
    
  # reset the state of the manager
  def reset(self):
    # a mapping from models to the views that represent them
    self._views = weakref.WeakValueDictionary()
    # the selected models
    self._selection = set()
    # a map of the context model in which an object was selected
    self._contexts = dict()
    # the model that's currently focused
    self._focused = None
    # whether the selection is being dragged
    self.dragging = False
    # whether snapping to event times is enabled
    self.snap_time = True
    # the time difference within which to snap, in seconds
    self.snap_window = 0.15
    # the time that has been snapped to
    self._snapped_time = None
    # make a stack to manage undo operations
    self._undo_stack = state.UndoStack()
    self._action_things = None
    self._end_action_timer = None
    
  # keep track of the views representing each model, keeping one entry
  #  for each view of a particular class representing a particular model
  def register_view(self, model, view):
    self._views[(model, view.__class__)] = view
  # get the view associated with the given model, 
  #  optionally selecting by view class
  def view_for_model(self, model, view_class=None):
    if (view_class is None):
      for (key, value) in self._views.iteritems():
        if (key[0] is model):
          return(value)
    else:
      try:
        return(self._views[(model, view_class)])
      except KeyError: return(None)
    return(None)
  # expose the selection as a property
  @property
  def selection(self):
    return(set(self._selection))
  @selection.setter
  def selection(self, new_selection):
    old_selection = set(self._selection)
    for item in new_selection:
      if (item in old_selection):
        old_selection.remove(item)
      else:
        self.select(item)
    for item in old_selection:
      self.deselect(item)
  # expose the selection contexts as a property 
  #  so it gets saved in undo state
  @property
  def contexts(self):
    return(self._contexts)
  @contexts.setter
  def contexts(self, value):
    self._contexts = value
  # expose the focused model as a property so it can be restored by undo
  @property
  def focused(self):
    return(self._focused)
  @focused.setter
  def focused(self, value):
    self._focused = value
    view = self.view_for_model(self._focused)
    if (view is not None):
      view.grab_focus()
  # deselect all selected objects
  def clear_selection(self):
    old_selection = set(self._selection)
    for item in old_selection:
      self.deselect(item)
  # add an object to the current selection
  def select(self, item, context=None):
    if (item is None): return
    if (item not in self._selection):
      self._selection.add(item)
      try:
        item.on_change()
      except AttributeError: pass
    if (context is not None):
      self._contexts[item] = context
  # deselect the given item
  def deselect(self, item):
    if (item is None): return
    if (item not in self._selection): return
    self._selection.remove(item)
    try:
      item.on_change()
    except AttributeError: pass
    if (item in self._contexts):
      del self._contexts[item]
  # toggle the selected state of all given items
  def toggle_select(self, item):
    if (item is None): return
    if (item in self._selection):
      self.deselect(item)
    else:
      self.select(item)
  # get the context in which the given item was selected
  def get_selected_context(self, item):
    try:
      return(self._contexts[item])
    except KeyError: return(None)
  # keep track of time snapping
  @property
  def snapped_time(self):
    return(self._snapped_time)
  @snapped_time.setter
  def snapped_time(self, value):
    if (value != self._snapped_time):
      self._snapped_time = value
      self.on_change()
  # expose properties of the undo stack, adding selection restoring
  #  and event grouping
  @property
  def can_undo(self):
    return(self._undo_stack.can_undo)
  @property
  def can_redo(self):
    return(self._undo_stack.can_redo)
  def undo(self, *args):
    self._undo_stack.undo()
    self.on_change()
  def redo(self, *args):
    self._undo_stack.redo()
    self.on_change()
  def begin_action(self, things=(), end_timeout=None):
    first_one = True
    if (end_timeout is not None):
      first_one = False
      if (self._end_action_timer is not None):
        GLib.source_remove(self._end_action_timer)
      else:
        first_one = True
      self._end_action_timer = GLib.timeout_add(
        end_timeout, self.end_action)
    elif (self._end_action_timer is not None):
      GLib.source_remove(self._end_action_timer)
      self._end_action_timer = None
      self.end_action()
    if (first_one):
      self._action_things = (things, self)
      self._undo_stack.begin_action(self._action_things)
      self.on_change()
  def end_action(self):
    self._undo_stack.end_action(self._action_things)
    self._action_things = None
    self.on_change()
    self._end_action_timer = None
    return(False)
  
# make a singleton instance
ViewManager = ViewManagerSingleton()

# make a mixin for transparent backgrounds
class Transparent(object):
  def make_transparent(self):
    style = self.get_style_context()
    normal_background = style.get_background_color(Gtk.StateFlags.NORMAL)
    selected_background = style.get_background_color(Gtk.StateFlags.SELECTED)
    transparent = Gdk.RGBA()
    transparent.red = normal_background.red
    transparent.green = normal_background.green
    transparent.blue = normal_background.blue
    transparent.alpha = 0.0
    selected_background.alpha = 0.99
    self.override_background_color(
      Gtk.StateFlags.NORMAL, transparent)
    self.override_background_color(
      Gtk.StateFlags.SELECTED, selected_background)
      
# make a mixin to traverse children and ancestors
class Traversable(object):
  # traverse parent widgets and return the nearest with the given attribute
  def get_parent_with_attribute(self, attr):
    node = self.get_parent()
    while (node):
      if (hasattr(node, attr)):
        return(node)
      node = node.get_parent()
    return(None)

# make a mixin for handling mouse events
class Interactive(object):
  # bind mouse events (this should be called in the constructor)
  def make_interactive(self):
    # initialize state
    self._down = None
    self.dragging = None
    # keep a dictionary of cursor areas
    self.cursor_areas = dict()
    # allow the control to receive focus
    self.set_can_focus(True)
    # hook to events
    self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                    Gdk.EventMask.POINTER_MOTION_MASK |
                    Gdk.EventMask.LEAVE_NOTIFY_MASK |
                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                    Gdk.EventMask.KEY_PRESS_MASK)
    self.connect('button-press-event', self.on_button_press)
    self.connect('motion-notify-event', self.on_pointer_motion)
    self.connect('leave-notify-event', self.on_leave)
    self.connect('button-release-event', self.on_button_release)
    self.connect('key-press-event', self.on_key_press)
  
  # handle keyboard events
  def on_key_press(self, widget, event):
    result = self.on_key(event.keyval, event.state)
    return(result)
  # override this and return True to handle keyboard input
  def on_key(self, keyval, state):
    return(False)
  
  # get the real coordinates of an event in this widget
  def get_pointer_coords(self):
    (win, x, y, state) = self.get_window().get_pointer()
    return(x, y)
  
  # handle mouse events
  def on_button_press(self, target, event):
    (x, y) = self.get_pointer_coords()
    # expose the context menu
    if (event.button == 3):
      return(self.on_context(event))
    # otherwise only register the primary button
    if (event.button != 1): return(False)
    self._down = {
      'x': x,
      'y': y,
      'x_root': event.x_root,
      'y_root': event.y_root,
      'state': event.state
    }
    self.dragging = None
  def on_pointer_motion(self, target, event):
    (x, y) = self.get_pointer_coords()
    if (target is not self):
      (found, x, y) = target.translate_coordinates(self, x, y)
    if (self._down is None):
      self.update_cursor(event.x, event.y, event.state)
      return
    if (self.dragging is None):
      dx = abs(x - self._down['x'])
      dy = abs(y - self._down['y'])
      if (max(dx, dy) > 6):
        self.dragging = self.start_drag(
          self._down['x'], self._down['y'],
          self._down['state'])
        if (self.dragging):
          self.grab_add()
    if (self.dragging):
      self.on_drag(event.x_root - self._down['x_root'], 
                   event.y_root - self._down['y_root'], 
                   event.state)
      return(True)
  def on_leave(self, target, event):
    self.update_cursor(-1000, -1000, 0)
  def on_button_release(self, target, event):
    if (self.dragging):
      self.grab_remove()
      self.dragging = None
      self._down = None
      self.on_drop()
      return(True)
    elif (self._down):
      result = None
      if ((event.x >= 0) and (event.x <= self._width) and 
          (event.y >= 0) and (event.y <= self._height) and 
          (abs(self._down['x_root'] - event.x_root) <= 6) and
          (abs(self._down['y_root'] - event.y_root) <= 6)):
        result = self.on_click(event.x, event.y, self._down['state'])
      self._down = None
      return(result)

  # override this to customize cursor behavior
  def update_cursor(self, x, y, state):
    for (area, cursor) in self.cursor_areas.iteritems():
      if ((x >= area.x) and (x <= area.x + area.width) and
          (y >= area.y) and (y <= area.y + area.height)):
        self.get_window().set_cursor(cursor)
        return
    self.get_window().set_cursor(None)
  # override this and return True to pop up a context menu
  def on_context(self, event):
    return(False)
  # override this and return True to handle clicks
  def on_click(self, x, y, state):
    return(False)
  # override this and return True to start handling a drag
  def start_drag(self, x, y, state):
    return(False)
  # override this to update a drag
  def on_drag(self, dx, dy, state):
    pass
  # override this to handle a drop
  def on_drop(self):
    pass

# aggregate the mixins for brevity
class View(Traversable, Transparent, Interactive):
  pass

# make a base class for views that do their own drawing
class DrawableView(View, Gtk.DrawingArea):
  def __init__(self, model=None):
    # store the model
    ViewManager.register_view(model, self)
    self._model = model
    if (model):
      try:
        self._model.add_observer(self.on_change)
      except AttributeError: pass
    # do base class configuration
    Gtk.DrawingArea.__init__(self)
    # handle redrawing
    self.connect('draw', self.on_draw)
    self.connect('state-changed', self.on_change)
    # keep track of the size at last redraw
    self._width = 0
    self._height = 0
  # expose the model the view is displaying as a read-only property
  @property
  def model(self):
    return(self._model)
  # call this to invalidate the view and schedule a redraw
  def on_change(self, *args):
    self.queue_draw()
  # handle redrawing requests
  def on_draw(self, widget, cr):
    self._width = self.get_allocated_width()
    self._height = self.get_allocated_height()    
    self.redraw(cr, self._width, self._height)
  # draw the view's contents into the given graphics context
  def redraw(self, cr, width, height):
    pass

# make a base class for views that just does layout for other views
class LayoutView(View, Gtk.Layout):
  def __init__(self, model):
    # store the model
    ViewManager.register_view(model, self)
    self._model = model
    try:
      self._model.add_observer(self.on_change)
    except AttributeError: pass
    # do base class configuration
    Gtk.Layout.__init__(self)
    self.connect('configure-event', self.on_change)
    self.connect('state-changed', self.on_change)
    self._layout_scheduled = False
    # keep track of the size at last layout
    self._width = 0
    self._height = 0
    # initialize storage for view pools
    self._view_pools = dict()
  # expose the model the view is displaying as a read-only property
  @property
  def model(self):
    return(self._model)
  # call this to schedule an update of the view's layout, 
  #  which is done after a delay to aggregate multiple quick changes
  def on_change(self, *args):
    if (not self._layout_scheduled):
      self._layout_scheduled = True
      GLib.idle_add(self._do_layout)
  def do_size_allocate(self, allocation):
    self.set_allocation(allocation)
    self.set_size(allocation.width, allocation.height)
    self._do_layout()
    if self.get_realized():
      self.get_window().move_resize(allocation.x, allocation.y,
                                    allocation.width, allocation.height)
      self.get_bin_window().resize(allocation.width, allocation.height)
  # update the cached size and run the layout code
  def _do_layout(self):
    size = self.get_size()
    self._width = size[0]
    self._height = size[1]
    self.layout(self._width, self._height)
    self.show_all()
    self._layout_scheduled = False
    # returning False makes this a one-shot event
    return(False)
  # override this to provide custom layout
  def layout(self, width, height):
    pass
  # traverse parent widgets and return the nearest with the given attribute
  def get_parent_with_attribute(self, attr):
    node = self.get_parent()
    while (node):
      if (hasattr(node, attr)):
        return(node)
      node = node.get_parent()
    return(None)
  # get list of views for each of the models in a list, removing any views
  #  of models that were in the list at last call and creating new views
  #  by passing the model to a function defined by the new_view_for_model param
  # NOTE: the list needs to be hashable like ModelList for this to work
  def allocate_views_for_models(self, models, new_view_for_model):
    # see if there's an entry in the pool for this list
    try:
      old_pool = self._view_pools[models]
    except KeyError:
      old_pool = dict()
    # add a view for each model
    views = [ ]
    new_pool = dict()
    for model in models:
      try:
        view = old_pool[model]
        del old_pool[model]
      except KeyError:
        view = new_view_for_model(model)
        self.add(view)
      new_pool[model] = view
      views.append(view)
    # remove all unused views
    for view in old_pool.itervalues():
      self.remove(view)
    # remember the new pool for next time
    self._view_pools[models] = new_pool
    return(views)
  # get the view associated with a single model from the given list
  def get_view_for_model(self, models, model):
    try:
      pool = self._view_pools[models]
      return(pool[model])
    except KeyError:
      return(None)

# make a base class for model-backed context menus
class ContextMenu(Gtk.Menu):
  def __init__(self, model):
    Gtk.Menu.__init__(self)
    self._model = model
    try:
      self._model.add_observer(self.on_change)
    except AttributeError: pass
  # expose the model the menu is presenting options for as a read-only property
  @property
  def model(self):
    return(self._model)
  # add a menu item and return it
  def make_item(self, label, callback):
    item = Gtk.MenuItem(label)
    item.connect('activate', callback)
    self.add(item)
    return(item)
    
  # override to update which menu actions are available based on model state
  def on_change(self):
    pass
    
    
# manage the layout of a list of items in one dimension
class ListLayout(object):
  def __init__(self, items):
    self._items = items
    # the default spacing in pixels between items
    self.spacing = 0
  # get the total number of pixels to allocate for am item
  def size_of_item(self, item):
    return(100)
  # convert between items and positions
  def position_of_item(self, item):
    p = 0
    for test_item in self._items:
      if (test_item is item):
        return(p)
      if (p > 0):
        p += self.spacing
      p += self.size_of_item(test_item)
    return(None)
  def center_of_item(self, item):
    return(self.position_of_item(item) +
            (self.size_of_item(item) / 2.0))
  def item_at_position(self, p):
    next_p = 0
    for item in self._items:
      if (p > 0):
        next_p += self.spacing
      next_p += self.size_of_item(item)
      if (p < next_p):
        return(item)
    return(None)
    
# show views from a list using a ListLayout
class ListView(LayoutView):
  def __init__(self, models, view_class, list_layout):
    LayoutView.__init__(self, models)
    self.make_interactive()
    self.list_layout = list_layout
    self.view_class = view_class
    self.drag_to_reorder = True
    self._dragging_item = None
    self._last_dy = 0
  def layout(self, width, height):
    views = self.allocate_views_for_models(
      self._model, 
      lambda t: self.view_class(t))
    for view in views:
      view.size_allocate(geom.Rectangle(
        0, self.list_layout.position_of_item(view.model),
        width, self.list_layout.size_of_item(view.model)))
  def start_drag(self, x, y, state):
    item = self.list_layout.item_at_position(y)
    if (item is None): return(False)
    self._dragging_item = item
    return(True)
  def on_drag(self, dx, dy, state):
    ddy = dy - self._last_dy
    jump = self.list_layout.size_of_item(self._dragging_item) / 2
    if (abs(ddy) < jump): return
    old_index = self._model.index(self._dragging_item)
    if (ddy < 0):
      new_index = max(0, old_index - 1)
    else:
      new_index = min(old_index + 1, len(self._model) - 1)
    if (new_index != old_index):
      new_list = list(self._model)
      del new_list[old_index]
      new_list.insert(new_index, self._dragging_item)
      self._model[0:] = new_list
      self._last_dy = dy
  def on_drop(self):
    self._dragging_item = None
    self._last_dy = 0
