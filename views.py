import math
import time
import cairo
import weakref

from gi.repository import Gtk, Gdk, GLib

import observable
import state
import geom

# make a singleton for handling things like selection state
class ViewManagerSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
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
    # allow the control to receive focus
    self.set_can_focus(True)
    # hook to events
    self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                    Gdk.EventMask.POINTER_MOTION_MASK |
                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                    Gdk.EventMask.KEY_PRESS_MASK)
    self.connect('button-press-event', self.on_button_press)
    self.connect('motion-notify-event', self.on_pointer_motion)
    self.connect('button-release-event', self.on_button_release)
    self.connect('key-press-event', self.on_key_press)
  
  # handle keyboard events
  def on_key_press(self, widget, event):
    return(self.on_key(event.keyval, event.state))
  # override this and return True to handle keyboard input
  def on_key(self, keyval, state):
    return(False)
    
  # handle mouse events
  def on_button_press(self, target, event):
    self._down = {
      'x': event.x,
      'y': event.y,
      'x_root': event.x_root,
      'y_root': event.y_root,
      'state': event.state
    }
    self.dragging = None
  def on_pointer_motion(self, target, event):
    if (self._down is None):
      return
    if (self.dragging is None):
      dx = abs(event.x - self._down['x'])
      dy = abs(event.y - self._down['y'])
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
  def on_button_release(self, target, event):
    if (self.dragging):
      self.grab_remove()
      self.dragging = None
      self._down = None
      self.on_drop()
      return(True)
    elif (self._down):
      result = None
      if ((not self.dragging) and 
            (event.x >= 0) and (event.x <= self._width) and 
            (event.y >= 0) and (event.y <= self._height)):
        result = self.on_click(event.x, event.y, self._down['state'])
      self._down = None
      return(result)

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
        self._model.add_listener(self.on_change)
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
  # draw a rounded rectangle
  def draw_round_rect(self, cr, x, y, w, h, r):
    degrees = math.pi / 180.0
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -90 * degrees, 0 * degrees)
    cr.arc(x + w - r, y + h - r, r, 0 * degrees, 90 * degrees)
    cr.arc(x + r, y + h - r, r, 90 * degrees, 180 * degrees)
    cr.arc(x + r, y + r, r, 180 * degrees, 270 * degrees)
    cr.close_path()

# make a base class for views that just does layout for other views
class LayoutView(View, Gtk.Layout):
  def __init__(self, model):
    # store the model
    ViewManager.register_view(model, self)
    self._model = model
    try:
      self._model.add_listener(self.on_change)
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

# make a view that shows the events in a block
class BlockView(DrawableView):
  def __init__(self, block):
    DrawableView.__init__(self, block)
    self._pitches = None
    self.make_transparent()
    self.make_interactive()
  # expose 'block' as an alternate name for 'model' for readability
  @property
  def block(self):
    return(self._model)
  # the list of pitches to display can be sourced from the block 
  #  or can be set externally, as when the block is part of a track
  @property
  def pitches(self):
    if (self._pitches != None):
      return(self._pitches)
    return(self.block.pitches)
  @pitches.setter
  def pitches(self, value):
    self._pitches = value
    self.on_change()
  # update selection state when changed
  def on_change(self, *args):
    if (self.block in ViewManager.selection):
      self.set_state(Gtk.StateType.SELECTED)
    else:
      self.set_state(Gtk.StateType.NORMAL)
    DrawableView.on_change(self)
  # get the height of a pitch
  @property
  def pitch_height(self):
    # divide the available space evenly between pitches
    try:
      return(int(math.floor(self._height / len(self.pitches))))
    except ZeroDivisionError:
      return(0)
  # map between a pitch and a y coordinate on the view
  def y_of_pitch(self, pitch):
    try:
      i = self.pitches.index(pitch)
    except ValueError:
      return(None)
    h = self.pitch_height
    return(self._height - int(math.ceil(h / 2)) - (i * h))
  def pitch_of_y(self, y):
    if (len(self.pitches) == 0):
      return(None)
    h = self.pitch_height
    y = self._height - y - int(math.ceil(h / 2))
    i = min(max(0, int(round(y / h))), len(self.pitches) - 1)
    return(self.pitches[i])
  # map between time and an x coordinate on the view
  def x_of_time(self, time):
    try:
      return(time * (self._width / self.block.duration))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(float(x) * (self.block.duration / float(self._width)))
    except ZeroDivisionError:
      return(0)
  # get the time in seconds at which the contents would repeat
  @property
  def repeat_time(self):
    return(self.block.events.duration)
  # get the width in pixels at which the contents would repeat
  @property
  def repeat_width(self):
    return(self.x_of_time(self.repeat_time))
  
  def redraw(self, cr, width, height):
    # get the colors to draw with
    style = self.get_style_context()
    state = self.get_state_flags()
    bg = style.get_background_color(state)
    fg = style.get_color(state)
    selected = ((state & Gtk.StateFlags.SELECTED) != 0)
    backdrop = ((state & Gtk.StateFlags.BACKDROP) != 0)
    # fill the background when selected
    if ((selected) and (not backdrop)):
      cr.set_source_rgba(bg.red, bg.green, bg.blue, 0.75)
      cr.rectangle(0, 0, width, height)
      cr.fill()
    # cache the pitch list for speed
    pitches = self.pitches
    # get the pitches that are being used in the block
    used_pitches = pitches
    if (self._pitches != None):
      used_pitches = set(self.block.pitches).intersection(pitches)
    # draw lines for all used pitches
    for pitch in used_pitches:
      y = self.y_of_pitch(pitch) - 0.5
      cr.set_line_width(1)
      cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
      cr.move_to(0, y)
      cr.line_to(width, y)
      cr.stroke()
    # draw lines for all divisions, if there are any
    divisions = self.block.events.divisions
    if (divisions > 0):
      x_step = self.x_of_time(self.repeat_time) / divisions
      x = 0
      while ((x_step > 0) and (x <= width)):
        px = round(x) + 0.5
        cr.set_line_width(1)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
        cr.move_to(px, 0)
        cr.line_to(px, height)
        cr.stroke()
        x += x_step
    # get the set of selected elements
    selection = ViewManager.selection
    # get the distance after which notes start being repeated
    repeat_width = self.repeat_width
    # draw boxes for all events with pitch
    for event in self.block.events:
      # skip events without pitch and time
      try:
        pitch = event.pitch
        time = event.time
      except AttributeError: continue
      if ((pitch is None) or (time is None)): continue
      # duration and velocity are optional
      duration = 0
      try:
        if (event.duration != None):
          duration = event.duration
      except AttributeError: pass
      velocity = 1
      try:
        if (event.velocity != None):
          velocity = event.velocity
      except AttributeError: pass
      # locate the beginning of the event
      x = self.x_of_time(time)
      y = self.y_of_pitch(pitch)
      # if its location is indeterminate, don't draw it
      if ((x is None) or (y is None)):
        continue
      x = round(x)
      # set the height of the event box based on velocity and center 
      #  it vertically on the guideline, leaving at max a pixel above and 
      #  below to separate from notes on other pitches
      h = (self.pitch_height - 2) * velocity
      y -= round(h / 2)
      # make sure all notes are at least as wide as they are tall
      w = round(self.x_of_time(time + duration)) - x
      w = max(w, h)
      # set the color depending on whether the note is selected
      if ((event in selection) and (not selected) and (not backdrop)):
        c = style.get_background_color(Gtk.StateFlags.SELECTED)
        cr.set_source_rgba(c.red, c.green, c.blue, 0.9)
      else:
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.9)
      # draw the note, repeating it as many times as needed
      while ((x < width) and (repeat_width > 0)):
        self.draw_round_rect(cr, x, y, w, h, 3)
        cr.fill()
        x += repeat_width
  
  # return the note(s) under the given position, if any
  def notes_at_pos(self, x, y):
    # convert the position to pitch and time
    time = self.time_of_x(x % self.repeat_width)
    pitch = self.pitch_of_y(y)
    if ((time is None) or (pitch is None)):
      return(())
    notes = [ ]
    # get the minimum duration of a note for it to be square
    #  (discounting that it may be drawn smaller to show velocity)
    min_duration = self.time_of_x(self.pitch_height)
    # find matching notes events
    for event in self.block.events:
      try:
        event_pitch = event.pitch
        event_time = event.time
      except AttributeError: continue
      event_duration = min_duration
      try:
        event_duration = max(min_duration, event.duration)
      except AttributeError: pass
      if ((pitch == event_pitch) and (time >= event_time) and
          (time <= event_time + event_duration)):
        notes.append(event)
    return(notes)
  # get the objects that could be selected if this position were clicked
  def selection_at_pos(self, x, y):
    notes = self.notes_at_pos(x, y)
    if (len(notes) > 0):
      return(notes)
    else:
      return((self.block,))
  
  # manage an undoable action for the selected items
  def get_toplevel_model(self):
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view): return(track_list_view.tracks)
    track_view = self.get_parent_with_attribute('track')
    if (track_view): return(track_view.track)
    return(self.block)
  def begin_action(self, end_timeout=None):
    ViewManager.begin_action(self.get_toplevel_model(), end_timeout)
  def end_action(self):
    ViewManager.end_action()
  
  # update selection when clicked
  def on_click(self, x, y, state):
    self.begin_action()
    self.select_at(x, y, state)
    self.end_action()
    return(True)
  def select_at(self, x, y, state):
    # update the selection
    targets = self.selection_at_pos(x, y)
    context = self.block
    if ((len(targets) > 0) and (targets[0] is self.block)):
      track_view = self.get_parent_with_attribute('track')
      if (track_view is not None):
        context = track_view.track
    if ((state & Gdk.ModifierType.CONTROL_MASK) != 0):
      if (len(targets) > 0):
        ViewManager.toggle_select(targets[0], context)
    elif ((state & Gdk.ModifierType.SHIFT_MASK) != 0):
      for target in targets:
        if (target not in ViewManager.selection):
          ViewManager.select(target, context)
          break
    else:
      ViewManager.clear_selection()
      ViewManager.select(targets[0], context)
    # give this view the input focus for keyboard commands
    ViewManager.focused = self.block
  # initiate dragging
  def start_drag(self, x, y, state):
    # store state before dragging starts
    self.begin_action()
    # update the selection based on the current click
    selection = ViewManager.selection
    dragging_selected = False
    events = self.notes_at_pos(x, y)
    if (len(events) > 0):
      for event in events:
        if (event in selection):
          dragging_selected = True
          self._dragging_target = event
          break
    elif (self.block in selection):
      dragging_selected = True
      self._dragging_target = self.block
    # if we're dragging what's already selected, all we need to do is make 
    #  sure we're never moving an event and the block it's in at the same time
    if (dragging_selected):
      for target in selection:
        if (hasattr(target, 'events')):
          for event in target.events:
            if (event in selection):
              ViewManager.deselect(target)
              break
    # if we're dragging an unselected item, clear and select it
    else:
      ViewManager.clear_selection()
      self.select_at(x, y, 0)
      for target in ViewManager.selection:
        self._dragging_target = target
        break
    # start dragging
    self._last_dx = 0
    self._last_dy = 0
    ViewManager.snapped_time = None
    ViewManager.dragging = True
    return(True)
  # handle dragging
  def on_drag(self, dx, dy, state):
    ddx = dx - self._last_dx
    ddy = dy - self._last_dy
    # get amounts to move in time/pitch/track space
    time_delta = self.get_time_delta(ddx)
    pitch_delta = self.get_pitch_delta(ddy)
    track_delta = self.get_track_delta(ddy)
    # see if the time of the dragged object can be snapped
    if (ViewManager.snap_time):
      if (ViewManager.snapped_time is None):
        target_time = None
        try:
          target_time = self._dragging_target.time
        except AttributeError: pass
        snap_delta = self.get_time_snap_delta(target_time)
        if ((snap_delta != 0) and (abs(snap_delta) < ViewManager.snap_window)):
          time_delta = snap_delta
          ViewManager.snapped_time = target_time + snap_delta
      else:
        if (abs(time_delta) > ViewManager.snap_window):
          ViewManager.snapped_time = None
        else:
          time_delta = 0
    # apply all deltas to the selection
    if ((time_delta != 0) or (pitch_delta != 0) or (track_delta != 0)):
      for target in ViewManager.selection:
        context = ViewManager.get_selected_context(target)
        if ((self.apply_time_delta(context, target, time_delta)) and 
            (ViewManager.snapped_time is None)):
          self._last_dx = dx
        if ((self.apply_pitch_delta(context, target, pitch_delta)) or
            (self.apply_track_delta(context, target, track_delta))):
          self._last_dy = dy
  # get the amount to adjust a given time to snap it to another feature
  def get_time_snap_delta(self, time):
    # try to get a list of all event times in the document
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view is None): return
    snap_times = track_list_view.tracks.times
    # find the delta to the one that's closest
    closest_delta = 0
    for snap_time in snap_times:
      delta = snap_time - time
      # ignore very small time differences
      if (abs(delta) < 0.0001): continue
      if ((closest_delta == 0) or (abs(delta) < abs(closest_delta))):
        closest_delta = delta
    return(closest_delta)
  # get the amount of time to move for the given x offset
  def get_time_delta(self, dx):
    if (abs(dx) >= 1.0):
      return(self.time_of_x(dx))
    else:
      return(0)
  # alter an object's time by the given number of steps
  def apply_time_delta(self, context, target, time_delta):
    if ((time_delta == 0) or (not hasattr(target, 'time'))):
      return
    one_pixel_time = self.time_of_x(1)
    time = max(0, target.time + time_delta)
    try:
      time = min(time, context.duration - one_pixel_time)
    except AttributeError: pass
    try:
      time = min(time, context.repeat_time - one_pixel_time)
    except AttributeError: pass
    if (time != target.time):
      target.time = time
      return(True)
  # get the number of pitch steps to move for the given y offset
  def get_pitch_delta(self, dy):
    pitch_delta = - (dy / self.pitch_height)
    if (abs(pitch_delta) > 0.5):
      if (pitch_delta > 0):
        return(int(math.ceil(pitch_delta)))
      else:
        return(int(math.floor(pitch_delta)))
    return(0)
  # alter an object's pitch by the given number of steps, defaulting to
  #  keeping to pitches that are already used in the current track
  def apply_pitch_delta(self, context, target, pitch_delta, 
                        existing_only=True):
    if ((pitch_delta == 0) or (not hasattr(target, 'pitch'))):
      return
    old_pitch = target.pitch
    if (existing_only):
      pitches = None
      view = ViewManager.view_for_model(context, self.__class__)
      if (view):
        pitches = view.pitches
      else:
        try:
          pitches = context.pitches
        except AttributeError: pass
      if (pitches is not None):
        old_pitch_index = pitches.index(target.pitch)
        pitch_index = min(max(
          0, old_pitch_index + pitch_delta), len(pitches) - 1)
        target.pitch = pitches[pitch_index]
        return(target.pitch != old_pitch)
    target.pitch = min(max(0, target.pitch + pitch_delta), 127)
    return(target.pitch != old_pitch)
  # get the track index of a block in a list of track
  def get_track_index(self, tracks, block=None):
    if (block is None):
      block = self.block
    i = 0
    for track in tracks:
      if (block in track):
        return(i)
      i += 1
    return(None)
  # get the number of track index positions to move for the given y offset
  def get_track_delta(self, dy):
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view is None): return
    tracks = track_list_view.tracks
    track_index = self.get_track_index(tracks)
    if (track_index == None): return
    # get the offsets into adjacent tracks
    current_y = track_list_view.y_of_track_index(track_index)
    if ((dy < 0) and (track_index > 0)):
      above_y = track_list_view.y_of_track_index(track_index - 1)
      if (abs(dy) > ((current_y - above_y) / 2)):
        return(-1)
    elif ((dy > 0) and (track_index < len(tracks) - 1)):
      below_y = track_list_view.y_of_track_index(track_index + 1)
      if (abs(dy) > ((below_y - current_y) / 2)):
        return(1)
    return(0)
  # alter an object's track number by the given number of steps
  def apply_track_delta(self, context, target, track_delta):
    # get the current track
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view is None): return
    tracks = track_list_view.tracks
    track_index = self.get_track_index(tracks, target)
    if (track_index == None): return
    # offset it
    new_track_index = min(max(0, track_index + track_delta), len(tracks) - 1)
    if (new_track_index != track_index):
      track_list_view.move_block(target, track_index, new_track_index)
      return(True)
  # store and show all changes when dragging stops
  def on_drop(self):
    ViewManager.snapped_time = None
    ViewManager.dragging = False
    # store state after dragging ends
    self.end_action()
    self.block.on_change()
    
  # handle keypresses while selected
  def on_key(self, keyval, state):
    # don't respond if nothing is selected
    if (len(ViewManager.selection) == 0):
      return(False)
    # delete things
    if ((keyval == Gdk.KEY_Delete) or (keyval == Gdk.KEY_BackSpace)):
      self.begin_action()
      for target in ViewManager.selection:
        context = ViewManager.get_selected_context(target)
        if (hasattr(context, 'events')):
          context.events.remove(target)
        else:
          context.remove(target)
      self.end_action()
      return(True)
    # move objects in time
    time_step = self.time_of_x(1)
    if (state == Gdk.ModifierType.SHIFT_MASK):
      time_step = float(self.repeat_time)
      if (self.block.events.divisions > 0):
        time_step /= self.block.events.divisions    
    time_delta = 0
    if (keyval == Gdk.KEY_Left):
      time_delta = - time_step
    elif (keyval == Gdk.KEY_Right):
      time_delta = time_step
    # move blocks in track space and notes in pitch space
    blocks_only = True
    notes_only = True
    for target in ViewManager.selection:
      if (hasattr(target, 'events')):
        notes_only = False
      elif (hasattr(target, 'pitch')):
        blocks_only = False
    track_delta = 0
    pitch_delta = 0
    if (keyval == Gdk.KEY_Up):
      if (blocks_only):
        track_delta = -1
      elif (notes_only):
        pitch_delta = 1
    elif (keyval == Gdk.KEY_Down):
      if (blocks_only):
        track_delta = 1
      elif (notes_only):
        pitch_delta = - 1
    # apply deltas to the selection
    if ((time_delta != 0) or (pitch_delta != 0) or (track_delta != 0)):
      # aggregate key presses that happen within 1 second of the last one
      self.begin_action(1000)
      # move items
      for target in ViewManager.selection:
        context = ViewManager.get_selected_context(target)
        self.apply_time_delta(context, target, time_delta)
        self.apply_pitch_delta(context, target, pitch_delta, 
                               existing_only=False)
        self.apply_track_delta(context, target, track_delta)
      return(True)

class TrackView(LayoutView):
  def __init__(self, track):
    LayoutView.__init__(self, track)
    self.make_transparent()
    self.make_interactive()
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  # map between time and an x coordinate on the view
  def x_of_time(self, time):
    try:
      return(time * (self._width / self.track.duration))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(float(x) * (self.track.duration / float(self._width)))
    except ZeroDivisionError:
      return(0)
  # get the height of a pitch
  @property
  def pitch_height(self):
    # divide the available space evenly between pitches
    try:
      return(int(math.floor(self._height / len(self.track.pitches))))
    except ZeroDivisionError:
      return(0)
  # map between a pitch and a y coordinate on the view
  def y_of_pitch(self, pitch):
    try:
      i = self.track.pitches.index(pitch)
    except ValueError:
      return(None)
    h = self.pitch_height
    return(self._height - int(math.ceil(h / 2)) - (i * h))
  def pitch_of_y(self, y):
    if (len(self.track.pitches) == 0):
      return(None)
    h = self.pitch_height
    y = self._height - y - int(math.ceil(h / 2))
    i = min(max(0, int(round(y / h))), len(self.track.pitches) - 1)
    return(self.track.pitches[i])
    
  # place blocks in the track
  def layout(self, width, height):
    # get views for the track's blocks and position them by time
    views = self.allocate_views_for_models(self.track, lambda b: BlockView(b))
    for view in views:
      if (view is None): continue
      x = self.x_of_time(view.block.time)
      r = geom.Rectangle(
        x, 0,
        self.x_of_time(view.block.time + view.block.duration) - x, height)
      view.size_allocate(r)
    # transfer track-wide pitch list to all views, 
    #  unless one of the views is being dragged 
    #  (we don't want to remove pitches while dragging)
    if (not ViewManager.dragging):
      pitches = self.track.pitches
      for view in views:
        view.pitches = pitches
    # update the header to show the new pitches
    header_view = ViewManager.view_for_model(self.track, TrackHeaderView)
    if (header_view is not None):
      header_view.on_change()

# manage the layout of a set of tracks so that it can be 
#  coordinated between the list and header views
class TrackLayout(object):
  def __init__(self, tracks):
    self.tracks = tracks
    # the spacing between tracks
    self.spacing = 4
  # get the total number of vertical pixels to allocate for the track
  def get_track_height(self, track):
    # always allocate a minimal amount of space for the header
    return(max(80, self.get_track_view_height(track)))
  # get the height to allocate for the track view itself
  def get_track_view_height(self, track):
    return(len(track.pitches) * 20)
  # convert between track indices and positions
  def y_of_track_index(self, track_index):
    y = None
    if ((track_index >= 0) and (track_index < len(self.tracks))):
      y = 0
      for i in range(0, track_index):
        y += self.spacing + self.get_track_height(self.tracks[i])
    return(y)
  def track_index_of_y(self, y):
    next_y = 0
    i = 0
    for track in self.tracks:
      if (i > 0):
        next_y += self.spacing
      next_y += self.get_track_height(track)
      if (y < next_y):
        return(i)
      i += 1
    return(None)

# display a list of tracks stacked vertically
class TrackListView(LayoutView):
  def __init__(self, tracks, transport=None, track_layout=None):
    LayoutView.__init__(self, tracks)
    self.track_layout = track_layout
    if (self.track_layout is None):
      self.track_layout = TrackLayout(self.tracks)
    # make a background view
    self.back = TrackListBackgroundView(self.tracks,
                                        transport=transport, 
                                        manager=ViewManager)
    self.back.x_of_time = self.x_of_time
    self.add(self.back)
    # receive events
    self.make_interactive()
  # expose 'tracks' as an alternate name for 'model' for readability
  @property
  def tracks(self):
    return(self._model)
  # map between time and an x coordinate on the view
  def x_of_time(self, time):
    try:
      return(time * (self._width / self.tracks.duration))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(float(x) * (self.tracks.duration / float(self._width)))
    except ZeroDivisionError:
      return(0)
  # map between track indices and a y coordinate on the view
  #  at the top of the track
  def y_of_track_index(self, track_index):
    return(self.track_layout.y_of_track_index(track_index))
  def track_index_of_y(self, y):
    return(self.track_layout.track_index_of_y(y))
  # place tracks in the view
  def layout(self, width, height):
    views = self.allocate_views_for_models(self.tracks, lambda t: TrackView(t))
    i = 0
    for view in views:
      track_height = self.track_layout.get_track_height(view.track)
      r = geom.Rectangle(
        0, self.track_layout.y_of_track_index(i),
        self.x_of_time(view.track.duration), 
        self.track_layout.get_track_view_height(view.track))
      r.y += round((track_height - r.height) / 2)
      view.size_allocate(r)
      i += 1
    self.back.size_allocate(geom.Rectangle(0, 0, width, height))
  # deselect when the user clicks
  def on_click(self, x, y, state):
    ViewManager.clear_selection()
    return(True)
  # move a block from one track to another
  def move_block(self, block, from_index, to_index):
    # get the associated views
    from_view = self.get_view_for_model(self.tracks, self.tracks[from_index])
    to_view = self.get_view_for_model(self.tracks, self.tracks[to_index])
    block_view = from_view.get_view_for_model(from_view.track, block)
    # store whether the view had focus
    had_focus = block_view.has_focus()
    # deselect the view if it was selected 
    #  (otherwise we seem to lose the alpha channel when it moves)
    was_selected = block_view.block in ViewManager.selection
    if (was_selected):
      ViewManager.deselect(block_view.block)
    # move the view from one view pool to another
    to_pool = to_view._view_pools[to_view.track]
    to_pool[block] = block_view
    from_pool = from_view._view_pools[from_view.track]
    del from_pool[block]
    # move the view from one to another
    block_view.reparent(to_view)
    # make the same change in the model layer
    from_view.track.remove(block)
    to_view.track.append(block)
    # restore the selection and focus state
    if (was_selected):
      ViewManager.select(block_view.block)
    if (had_focus):
      block_view.grab_focus()

# display a background behind a list of tracks
class TrackListBackgroundView(DrawableView):
  def __init__(self, tracks, transport=None, manager=None):
    DrawableView.__init__(self, tracks)
    self.transport = transport
    if (transport):
      self.transport.add_listener(self.on_change)
    self.manager = manager
    if (manager):
      self.manager.add_listener(self.on_change)
    self.x_of_time = lambda self, x: x
  # expose 'tracks' as an alternate name for 'model'
  @property
  def tracks(self):
    return(self._model)
  # draw guide markers in the background
  def redraw(self, cr, width, height):
    # get colors
    style = self.get_style_context()
    fg = style.get_color(Gtk.StateType.NORMAL)
    backdrop = ((self.get_state_flags() & Gtk.StateFlags.BACKDROP) != 0)
    fade = 1.0
    if (backdrop):
      fade = 0.25
    # draw backgrounds behind the tracks to show their states
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view is not None):
      i = 0
      for track in self.tracks:
        r = geom.Rectangle(0, track_list_view.y_of_track_index(i), 
              width, track_list_view.track_layout.get_track_height(track))
        if (track.arm):
          cr.set_source_rgba(1.0, 0.0, 0.0, 0.25 * fade)
          cr.rectangle(r.x, r.y, r.width, r.height)
          cr.fill()
        if (not track.enabled):
          cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.25 * fade)
          cr.rectangle(r.x, r.y, r.width, r.height)
          cr.fill()
        i += 1
    # draw transport state
    if (self.transport):
      # draw the transport's current time point with a fill on the left
      #  so we can easily see whether we're before or after it
      x = max(1, round(self.x_of_time(self.transport.time)))
      cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1 * fade)
      cr.rectangle(0, 0, x, height)
      cr.fill()
      cr.set_source_rgba(1.0, 0.0, 0.0, 0.75 * fade)
      cr.set_line_width(2)
      cr.move_to(x, 0)
      cr.line_to(x, height)
      cr.stroke()
      # draw all the marks on the transport
      for t in self.transport.marks:
        x = round(self.x_of_time(t))
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75 * fade)
        cr.set_dash((2, 2))
        cr.set_line_width(2)
        cr.move_to(x, 0)
        cr.line_to(x, height)
        cr.stroke()
    if (self.manager):
      # draw the snap indicator
      snapped_time = ViewManager.snapped_time
      if (snapped_time is not None):
        x = round(self.x_of_time(snapped_time)) + 0.5
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75 * fade)
        cr.set_line_width(1)
        cr.set_dash((2, 3))
        cr.move_to(x, 0)
        cr.line_to(x, height)
        cr.stroke()
  
# display a header with general track information
class TrackHeaderView(DrawableView):
  def __init__(self, track, track_view):
    DrawableView.__init__(self, track)
    self.track_view = track_view
    self.level_rect = geom.Rectangle()
    self.pan_rect = geom.Rectangle()
    self.mute_rect = geom.Rectangle()
    self.solo_rect = geom.Rectangle()
    self.arm_rect = geom.Rectangle()
    self.pitches_area = geom.Rectangle()
    self.pitch_areas = [ ]
    self._draggable_areas = ( self.level_rect, self.pan_rect )
    self._dragging_target = None
    self.make_interactive()
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  # draw the header
  def redraw(self, cr, width, height):
    # get style
    style = self.get_style_context()
    fg = style.get_color(self.get_state())
    # allocate horizontal space
    level_width = 20
    button_width = 20
    spacing = 4
    button_spacing = 4
    # place the pan/level bar
    x = spacing
    self.pan_rect.x = x
    self.pan_rect.y = 0
    self.pan_rect.width = self.pan_rect.height = level_width
    self.level_rect.x = x
    self.level_rect.y = self.pan_rect.y + self.pan_rect.height
    self.level_rect.width = level_width
    self.level_rect.height = height - self.pan_rect.height
    x += level_width + spacing
    # place the track mode buttons
    button_size = min(button_width, 
      math.floor((height - (2 * button_spacing)) / 3))
    self.mute_rect.width = self.mute_rect.height = button_size
    self.solo_rect.width = self.solo_rect.height = button_size
    self.arm_rect.width = self.arm_rect.height = button_size
    y = height - 1
    y -= button_size
    self.arm_rect.x = x
    self.arm_rect.y = y
    y -= button_size + button_spacing
    self.mute_rect.x = x
    self.mute_rect.y = y
    y -= button_size + button_spacing
    self.solo_rect.x = x
    self.solo_rect.y = y
    x += button_width + spacing
    # place the pitch labels as a group
    self.pitches_area.x = x
    self.pitches_area.y = 0
    self.pitches_area.height = height
    self.pitches_area.width = width - x
    # draw the pan control
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
    cr.set_line_width(2)
    x = self.pan_rect.x + (self.pan_rect.width / 2)
    x += self.track.pan * ((self.pan_rect.width / 2) - 1)
    x = round(x)
    cr.move_to(x, self.pan_rect.y)
    cr.line_to(x, self.pan_rect.y + self.pan_rect.height)
    cr.stroke()
    # draw the mixer bar
    h = max(2, round(self.level_rect.height * self.track.level))
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.25)
    y = self.level_rect.y + self.level_rect.height - h
    cr.rectangle(self.level_rect.x, y, self.level_rect.width, h)
    cr.fill()
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
    y += 1
    cr.set_line_width(2)
    cr.move_to(self.level_rect.x, y)
    cr.line_to(self.level_rect.x + self.level_rect.width, y)
    cr.stroke()
    # draw the buttons
    self.draw_button(cr, self.mute_rect, 'M', fg, self.track.mute)
    self.draw_button(cr, self.solo_rect, 'S', fg, self.track.solo)
    self.draw_button(cr, self.arm_rect, 'R', fg, self.track.arm)
    # draw the pitch labels
    self.pitch_areas = [ ]
    ty = 0
    if (self.track_view):
      cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.5)
      font_size = math.floor(self.track_view.pitch_height * 0.75)
      cr.set_font_size(font_size)
      x = self.pitches_area.x + self.pitches_area.width - round(font_size / 2)
      ty = (height - self.track_view._height) / 2
      for pitch in self.track.pitches:
        py = self.track_view.y_of_pitch(pitch)
        if (py is None): continue
        y = ty + py
        name = self.track.name_of_pitch(pitch)
        (bx, by, tw, th, nx, ny) = cr.text_extents(name)
        cr.move_to(
          x - tw - bx, 
          y - (th / 2) - by)
        cr.show_text(name)
  
  def draw_button(self, cr, area, label, color, toggled):
    radius = 3
    cr.set_source_rgba(color.red, color.green, color.blue, 0.1)
    self.draw_round_rect(cr, area.x, area.y, area.width, area.height, radius)
    cr.fill()
    if (toggled):
      cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
      cr.set_line_width(2)
      self.draw_round_rect(cr, area.x, area.y, area.width, area.height, radius)
      cr.stroke()
    if (len(label) > 0):
      if (toggled):
        cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
      else:
        cr.set_source_rgba(color.red, color.green, color.blue, 0.5)
      cr.set_font_size(round(min(area.width, area.height) / 2))
      (bx, by, tw, th, nx, ny) = cr.text_extents(label)
      cr.move_to(area.x + (area.width / 2) - (tw / 2) - bx, 
                 area.y + (area.height / 2) - (th / 2) - by)
      cr.show_text(label)
  
  # edit track properties by clicking
  def on_click(self, x, y, state):
    if (self.mute_rect.contains(x, y)):
      self.track.mute = not self.track.mute
      return(True)
    elif (self.solo_rect.contains(x, y)):
      self.track.solo = not self.track.solo
      return(True)
    elif (self.arm_rect.contains(x, y)):
      self.track.arm = not self.track.arm
      return(True)
  
  # edit track properties by dragging
  def start_drag(self, x, y, state):
    self._last_dx = 0
    self._last_dy = 0
    for area in self._draggable_areas:
      if (area.contains(x, y)):
        self._dragging_target = area
        self._original_level = self.track.level
        self._original_pan = self.track.pan
        return(True)
    self._dragging_target = self
    return(True)
  def on_drag(self, dx, dy, state):
    if (self._dragging_target is self):
      ddy = dy - self._last_dy
      track_delta = 0
      if (ddy < - (self._height / 2)):
        track_delta = -1
      elif (ddy > (self._height / 2)):
        track_delta = 1
      if (self.apply_track_delta(track_delta)):
        self._last_dy = dy
    else:
      area = self._dragging_target
      # holding down control moves in finer increments
      if ((state & Gdk.ModifierType.CONTROL_MASK) != 0):
        dx *= 0.5
        dy *= 0.5
      if (area is self.level_rect):
        self.track.level = min(max(
          0, self._original_level - (dy / area.height)), 1)
      elif (area is self.pan_rect):
        self.track.pan = min(max(
          -1, self._original_pan + (dx / area.width)), 1)
  # move the track up and down in the list
  def apply_track_delta(self, track_delta):
    if (track_delta == 0):
      return(False)
    track_list_view = self.get_parent_with_attribute('tracks')
    if (track_list_view is None):
      return(False)
    tracks = track_list_view.tracks
    index = tracks.index(self.track)
    new_index = min(max(0, index + track_delta), len(tracks) - 1)
    if (new_index != index):
      new_tracks = list(tracks)
      del new_tracks[index]
      new_tracks.insert(new_index, self.track)
      tracks[0:] = new_tracks
      return(True)
    return(False)
    
# display a list of track headers
class TrackListHeaderView(LayoutView):
  def __init__(self, tracks, track_layout=None):
    LayoutView.__init__(self, tracks)
    self.track_layout = track_layout
    if (self.track_layout is None):
      self.track_layout = TrackLayout(self.tracks)
  # expose 'tracks' as an alternate name for 'model' for readability
  @property
  def tracks(self):
    return(self._model)
  # map between track indices and a y coordinate on the view
  #  at the top of the track
  def y_of_track_index(self, track_index):
    return(self.track_layout.y_of_track_index(track_index))
  def track_index_of_y(self, y):
    return(self.track_layout.track_index_of_y(y))
  # place tracks in the view
  def layout(self, width, height):
    views = self.allocate_views_for_models(
      self.tracks, 
      lambda t: TrackHeaderView(t, None))
    i = 0
    for view in views:
      view.track_view = ViewManager.view_for_model(view.track, TrackView)
      view.size_allocate(geom.Rectangle(
        0, self.track_layout.y_of_track_index(i),
        width, self.track_layout.get_track_height(view.track)))
      i += 1
  
