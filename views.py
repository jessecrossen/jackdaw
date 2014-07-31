import math
import time
import cairo
import weakref

from gi.repository import Gtk, Gdk, GLib

import observable
import state

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
    # initialize the layout cache
    self._pitch_height = 0
    self._pitch_to_y = dict()
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
  
  # map between a pitch and a y coordinate on the view
  def y_of_pitch(self, pitch):
    try:
      return(self._pitch_to_y[pitch])
    except KeyError:
      return(None)
  def pitch_of_y(self, y):
    closest = None
    closest_distance = None
    for (pitch, pitch_y) in self._pitch_to_y.iteritems():
      distance = abs(y - pitch_y)
      if ((closest_distance is None) or (distance < closest_distance)):
        closest_distance = distance
        closest = pitch
    return(closest)
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
    # fill the background when selected
    if (bg.alpha > 0):
      cr.set_source_rgba(bg.red, bg.green, bg.blue, 0.75)
      cr.rectangle(0, 0, width, height)
      cr.fill()
    # cache the pitch list for speed
    pitches = self.pitches
    # divide the available space evenly between pitches
    try:
      self._pitch_height = int(math.floor(height / len(pitches)))
    except ZeroDivisionError:
      self._pitch_height = 0
    # map pitches to y coordinates
    self._pitch_to_y = dict()
    y = height - int(math.ceil(self._pitch_height / 2))
    for pitch in pitches:
      self._pitch_to_y[pitch] = y
      y -= self._pitch_height
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
      h = (self._pitch_height - 2) * velocity
      y -= round(h / 2)
      # make sure all notes are at least as wide as they are tall
      w = round(self.x_of_time(time + duration)) - x
      w = max(w, h)
      # set the color depending on whether the note is selected
      if ((event in selection) and (self.block not in selection)):
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
    min_duration = self.time_of_x(self._pitch_height)
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
    self.end_action()
    return(True)
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
      self.on_click(x, y, 0)
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
    pitch_delta = - (dy / self._pitch_height)
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
    self.track.add_listener(self.on_track_change)
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
  # map between pitch and a y coordinate on the view
  def y_of_pitch(self, pitch):
    if (len(self.blocks) > 0):
      view = self.get_view_for_model(self.blocks, self.blocks[0])
      if (view is not None):
        return(view.y_of_pitch(pitch))
    return(None)
  def pitch_of_y(self, y):
    if (len(self.blocks) > 0):
      view = self.get_view_for_model(self.blocks, self.blocks[0])
      if (view is not None):
        return(view.pitch_of_y(y))
    return(None)
  # update from a change to the track
  def on_track_change(self):
    # change the background to indicate track state   
    style = self.get_style_context() 
    default_bg = style.get_background_color(self.get_state())
    normal_fg = style.get_color(Gtk.StateType.NORMAL)
    bg = Gdk.RGBA()
    bg.red = default_bg.red
    bg.green = default_bg.green
    bg.blue = default_bg.blue
    bg.alpha = 0.0
    if (self.track.arm):
      bg.red = 1.0
      bg.green = 0.0
      bg.blue = 0.0
      bg.alpha = 0.25
    elif (not self.track.enabled):
      bg.red = normal_fg.red
      bg.green = normal_fg.green
      bg.blue = normal_fg.blue
      bg.alpha = 0.25
    self.override_background_color(Gtk.StateFlags.NORMAL, bg)
  # place blocks in the track
  def layout(self, width, height):
    # get views for the track's blocks and position them by time
    views = self.allocate_views_for_models(self.track, lambda b: BlockView(b))
    for view in views:
      if (view is None): continue
      r = Gdk.Rectangle()
      r.x = self.x_of_time(view.block.time)
      r.y = 0
      r.width = self.x_of_time(view.block.time + view.block.duration) - r.x
      r.height = height
      view.size_allocate(r)
    # transfer track-wide pitch list to all views, 
    #  unless one of the views is being dragged 
    #  (we don't want to remove pitches while dragging)
    if (not ViewManager.dragging):
      pitches = self.track.pitches
      for view in views:
        view.pitches = pitches

# manage the layout of a set of tracks so that it can be 
#  coordinated between the list and header views
class TrackLayout(object):
  def __init__(self, tracks):
    self.tracks = tracks
  # get the total number of vertical pixels to allocate for the track
  def get_track_height(self, track):
    # always allocate a minimal amount of space for the header
    return(max(60, self.get_track_view_height(track)))
  # get the height to allocate for the track view itself
  def get_track_view_height(self, track):
    return(len(track.pitches) * 20)
  # convert between track indices and positions
  def y_of_track_index(self, track_index):
    y = None
    if ((track_index >= 0) and (track_index < len(self.tracks))):
      y = 0
      for i in range(0, track_index):
        y += self.get_track_height(self.tracks[i])
    return(y)
  def track_index_of_y(self, y):
    next_y = 0
    i = 0
    for track in self.tracks:
      next_y += self.get_track_height(track)
      if (y < next_y):
        return(i)
      i += 0
    return(None)

# display a list of tracks stacked vertically
class TrackListView(LayoutView):
  def __init__(self, tracks, transport=None, mixer=None, track_layout=None):
    LayoutView.__init__(self, tracks)
    self.mixer = mixer
    if (self.mixer):
      self.mixer.add_listener(self.on_change)
    self.track_layout = track_layout
    if (self.track_layout is None):
      self.track_layout = TrackLayout(self.tracks)
    # make a background view
    self.back = TrackListBackgroundView(transport=transport, 
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
    y = 0
    for view in views:
      r = Gdk.Rectangle()
      track_height = self.track_layout.get_track_height(view.track)
      r.x = 0
      r.y = self.track_layout.y_of_track_index(i)
      r.width = self.x_of_time(view.track.duration)
      r.height = self.track_layout.get_track_view_height(view.track)
      r.y += round((track_height - r.height) / 2)
      view.size_allocate(r)
      i += 1
      y += track_height
    r = Gdk.Rectangle()
    r.width = width
    r.height = height
    self.back.size_allocate(r)
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
  def __init__(self, transport=None, manager=None):
    DrawableView.__init__(self, transport)
    self.transport = transport
    if (transport):
      self.transport.add_listener(self.on_change)
    self.manager = manager
    if (manager):
      self.manager.add_listener(self.on_change)
    self.x_of_time = lambda self, x: x
  # draw guide markers in the background
  def redraw(self, cr, width, height):
    style = self.get_style_context()
    fg = style.get_color(Gtk.StateType.NORMAL)
    if (self.transport):
      # draw the transport's current time point with a fill on the left
      #  so we can easily see whether we're before or after it
      x = round(self.x_of_time(self.transport.time))
      cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
      cr.rectangle(0, 0, x, height)
      cr.fill()
      cr.set_source_rgba(1.0, 0.0, 0.0, 0.75)
      cr.set_line_width(2)
      cr.move_to(x, 0)
      cr.line_to(x, height)
      cr.stroke()
      # draw all the marks on the transport
      for t in self.transport.marks:
        x = round(self.x_of_time(t))
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75)
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
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75)
        cr.set_line_width(1)
        cr.set_dash((2, 3))
        cr.move_to(x, 0)
        cr.line_to(x, height)
        cr.stroke()
  
# display a header with general track information
class TrackHeaderView(LayoutView):
  def __init__(self, track, track_view):
    LayoutView.__init__(self, track)
    self.track_view = track_view
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
    
# display a list of track headers
class TrackListHeaderView(LayoutView):
  def __init__(self, track_list, track_layout=None):
    LayoutView.__init__(self, track)
    self.track_layout = track_layout
    if (self.track_layout is None):
      self.track_layout = TrackLayout(self.tracks)
  # expose 'tracks' as an alternate name for 'model' for readability
  @property
  def tracks(self):
    return(self._model)
  
