import math

from gi.repository import Gtk, Gdk

from ..common import observable
import geom
import symbols
from core import DrawableView, ContextMenu, ViewManager, TimeScale

# make a view that shows the events in a block
class BlockView(DrawableView):
  def __init__(self, block, time_scale):
    DrawableView.__init__(self, block)
    self.make_transparent()
    self.make_interactive()
    self.time_scale = time_scale
    self.time_scale.add_observer(self.on_change)
    self._menu = None
    self._pitches = None
    self.ending = observable.AttributeProxy(
      self.block, 'time', 'duration')
    self.ending_area = geom.Rectangle(x=-100, width=6)
    self.beginning_area = geom.Rectangle(x=-100, width=6)    
    self.cursor_areas[self.ending_area] = Gdk.Cursor.new(
      Gdk.CursorType.RIGHT_SIDE)
    self.repeat = None
    self.repeat_area = geom.Rectangle(x=-100, width=6)
    
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
      return(1 + self.time_scale.x_of_time(time))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(self.time_scale.time_of_x(x - 1))
    except ZeroDivisionError:
      return(0)
  # get the time in seconds at which the contents would repeat
  @property
  def repeat_time(self):
    return(self.block.events.duration)
  # get the width in pixels at which the contents would repeat
  @property
  def repeat_width(self):
    return(self.time_scale.x_of_time(self.repeat_time))
  
  def redraw(self, cr, width, height):
    # get the colors to draw with
    style = self.get_style_context()
    state = self.get_state_flags()
    bg = style.get_background_color(state)
    fg = style.get_color(state)
    selected = ((state & Gtk.StateFlags.SELECTED) != 0)
    backdrop = ((state & Gtk.StateFlags.BACKDROP) != 0)
    selection = ViewManager.selection
    # set up cairo to paint the given object
    def set_color_for(obj, alpha=1.0):
      if ((obj in selection) and (not selected) and (not backdrop)):
        c = style.get_background_color(Gtk.StateFlags.SELECTED)
        cr.set_source_rgba(c.red, c.green, c.blue, alpha)
      else:
        cr.set_source_rgba(fg.red, fg.green, fg.blue, alpha)
    # fill the background when selected
    if (selected):
      cr.set_source_rgba(bg.red, bg.green, bg.blue, 0.75)
    else:
      set_color_for(None, 0.05)
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
      x_step = self.repeat_width / divisions
      x = 0
      while ((x_step > 0) and (x <= width)):
        px = round(x) + 0.5
        cr.set_line_width(1)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
        cr.move_to(px, 0)
        cr.line_to(px, height)
        cr.stroke()
        x += x_step
    # get the distance after which notes start being repeated
    repeat_width = self.repeat_width
    # draw the repeat sign
    if (self.repeat_time < self.ending.time):
      set_color_for(self.repeat, 0.75)
      self.repeat_area.x = (
        self.x_of_time(self.repeat_time) - self.repeat_area.width)
      self.repeat_area.height = self._height
      symbols.draw_repeat(cr, self.repeat_area)
    # draw end caps
    set_color_for(None, 0.75)
    self.beginning_area.x = self.x_of_time(0) - 1
    self.beginning_area.height = height
    symbols.draw_cap(cr, self.beginning_area, 1)
    set_color_for(self.ending, 0.75)
    x = self.x_of_time(self.ending.time) + 1
    self.ending_area.x = x - self.ending_area.width
    self.ending_area.height = height
    symbols.draw_cap(cr, self.ending_area, -1)
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
      # locate the beginning of the event
      x = self.x_of_time(time)
      y = self.y_of_pitch(pitch)
      # if its location is indeterminate, don't draw it
      if ((x is None) or (y is None)):
        continue
      x = round(x)
      # center the event vertically on the guideline
      h = self.pitch_height
      y -= round(h / 2)
      w = round(self.x_of_time(time + duration)) - x
      # set the color depending on whether the note is selected
      set_color_for(event, 0.9)
      area = geom.Rectangle(x, y, w, h)
      # draw the note, repeating it as many times as needed
      while ((area.x < width) and (repeat_width > 0)):
        symbols.draw_note(cr, event, area)
        area.x += repeat_width
    
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
    if (self.ending_area.contains(x, y)):
      return((self.ending,))
    if (self.repeat_area.contains(x, y)):
      if ((self.repeat is None) or 
          (self.repeat.target is not self.block.events)):
        self.repeat = observable.AttributeProxy(
          self.block.events, 'time', 'duration')
      return((self.repeat,))
    # if nothing else is under the selection, select the block itself
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
    ViewManager.focused = self.block
    self.end_action()
    return(True)
  def select_at(self, x, y, state):
    # update the selection
    targets = self.selection_at_pos(x, y)
    context = self.block
    target = targets[0] if len(targets) > 0 else None
    if ((target is self.block) or (target is self.ending)):
      track_view = self.get_parent_with_attribute('track')
      if (track_view is not None):
        context = track_view.track
    if ((state & Gdk.ModifierType.CONTROL_MASK) != 0):
      if (len(targets) > 0):
        ViewManager.toggle_select(target, context)
    elif ((state & Gdk.ModifierType.SHIFT_MASK) != 0):
      for target in targets:
        if (target not in ViewManager.selection):
          ViewManager.select(target, context)
          break
    else:
      ViewManager.clear_selection()
      ViewManager.select(target, context)
    # give this view the input focus for keyboard commands
    ViewManager.focused = self.block
  # initiate dragging
  def start_drag(self, x, y, state):
    # store state before dragging starts
    self.begin_action()
    # update the selection based on the current click
    ViewManager.focused = self.block
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
        else:
          self._snap_delta = self.get_time_snap_delta(target_time)
          if ((self._snap_delta != 0) and 
              (abs(self._snap_delta) < ViewManager.snap_window)):
            time_delta = self._snap_delta
            ViewManager.snapped_time = target_time + self._snap_delta
      else:
        if (abs(time_delta - self._snap_delta) > ViewManager.snap_window):
          ViewManager.snapped_time = None
          time_delta -= self._snap_delta
          self._snap_delta = 0
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
      return(self.time_of_x(self.x_of_time(0.0) + dx))
    else:
      return(0)
  # alter an object's time by the given number of steps
  def apply_time_delta(self, context, target, time_delta):
    if ((time_delta == 0) or (not hasattr(target, 'time'))):
      return
    time = max(0, target.time + time_delta)
    if ((target is not self.repeat) and (target is not self.ending)):
      one_pixel_time = self.time_of_x(1) - self.time_of_x(0)
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
    time_step = self.time_of_x(1) - self.time_of_x(0)
    alter_divisions = False
    if (state == Gdk.ModifierType.SHIFT_MASK):
      time_step = float(self.repeat_time)
      if (self.block.events.divisions > 0):
        time_step /= self.block.events.divisions
        if (self.repeat in ViewManager.selection):
          alter_divisions = True
    time_delta = 0
    if (keyval == Gdk.KEY_Left):
      time_delta = - time_step
      if ((alter_divisions) and (self.block.events.divisions > 1)):
        self.block.events.divisions -= 1
    elif (keyval == Gdk.KEY_Right):
      time_delta = time_step
      if (alter_divisions):
        self.block.events.divisions += 1
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
    return(False)

  # show a context menu for the block
  def on_context(self, event):
    if (self._menu is None):
      tracks = None
      tracks_view = self.get_parent_with_attribute('tracks')
      if (tracks_view):
        tracks = tracks_view.tracks
      self._menu = BlockMenu(self.block, tracks=tracks)
    self._menu.on_change()
    self._menu.popup(None, None, None, None, 
                     event.button, event.time)

# make a context menu for blocks
class BlockMenu(ContextMenu):
  def __init__(self, block, tracks=None):
    ContextMenu.__init__(self, block)
    self.tracks = tracks
    # add menu items
    self.join_item = self.make_item('Join', self.on_join)
    self.split_item = self.make_item('Split', self.on_split)
    self.show_all()
  @property
  def block(self):
    return(self._model)
  def on_change(self):
    # get all the selected blocks
    selected = self.get_selected_blocks()
    # if the block is the only one selected it can be split
    self.split_item.set_sensitive((len(selected) == 0) or 
      ((len(selected) == 1) and (self.block in selected)))
    # if more than one block is selected, they can be joined
    self.join_item.set_sensitive(
      (len(selected) == 0) or (self.block in selected))
  # get all blocks in the selection
  def get_selected_blocks(self):
    blocks = set()
    for item in ViewManager.selection:
      if (hasattr(item, 'events')):
        blocks.add(item)
    return(blocks)
  # get selected events within the current block
  def get_selected_notes(self):
    block_events = set(self.block.events)
    selected_events = set()
    for item in ViewManager.selection:
      if ((item in block_events) and (hasattr(item, 'pitch'))):
        selected_events.add(item)
    return(selected_events)
  # join multiple blocks
  def on_join(self, *args):
    blocks = self.get_selected_blocks()
    blocks.add(self.block)
    ViewManager.begin_action((blocks, self.tracks))
    if (len(blocks) > 1):
      self.block.join(blocks, tracks=self.tracks)
    else:
      self.block.join_repeats()
    ViewManager.end_action()
  # split a block at selected note boundaries
  def on_split(self, *args):
    # find the track this block is in so we can place 
    #  the new split-off blocks somewhere
    track = None
    if (self.tracks):
      for search_track in self.tracks:
        if (self.block in search_track):
          track = search_track
          break
    if (track is None): return
    # if the block has multiple repeats, split the repeats
    if (self.block.events.duration < self.block.duration):
      ViewManager.begin_action(track)
      self.block.split_repeats(track=track)
      ViewManager.end_action()
    else:
      times = [ ]
      # get selected events in the block
      selected_events = self.get_selected_notes()
      # if events are selected in the block, find boundaries 
      #  between selected and deselected events
      if (len(selected_events) > 0):
        # sort all block events by time
        events = list(self.block.events)
        events.sort(key=lambda e: e.time)
        # find boundaries
        was_selected = (events[0] in selected_events)
        for event in events:
          # count notes only
          if (not hasattr(event, 'pitch')): continue
          is_selected = (event in selected_events)
          if (is_selected != was_selected):
            times.append(event.time)
            was_selected = is_selected
      # if there are times to split on, we can split
      if (len(times) > 0):
        ViewManager.begin_action((self.block, track))
        self.block.split(times, track=track)
        ViewManager.end_action()
