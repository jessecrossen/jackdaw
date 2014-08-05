import math
import cairo

from gi.repository import Gtk, Gdk

import geom
from core import DrawableView, LayoutView, ViewManager, ListLayout
import block

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
      return(1 + (time * ((self._width - 2) / self.track.duration)))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(float(x - 1) * (self.track.duration / float(self._width - 2)))
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
    views = self.allocate_views_for_models(self.track, lambda b: block.BlockView(b))
    for view in views:
      if (view is None): continue
      x = self.x_of_time(view.block.time)
      w = self.x_of_time(view.block.time + view.block.duration) - x
      r = geom.Rectangle(x - 1, 0, w + 2, height)
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
class TrackLayout(ListLayout):
  def __init__(self, tracks):
    ListLayout.__init__(self, tracks)
    self.tracks = tracks
    # add spacing between tracks
    self.spacing = 4
  # get the total number of vertical pixels to allocate for the track
  def size_of_item(self, track):
    # always allocate a minimal amount of space for the header
    return(max(80, self.size_of_track_view(track)))
  # get the height to allocate for the track view itself
  def size_of_track_view(self, track):
    return(len(track.pitches) * 20)

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
      return(1 + (time * ((self._width - 2) / self.tracks.duration)))
    except ZeroDivisionError:
      return(0)
  def time_of_x(self, x):
    try:
      return(float(x - 1) * (self.tracks.duration / float(self._width - 2)))
    except ZeroDivisionError:
      return(0)
  # place tracks in the view
  def layout(self, width, height):
    views = self.allocate_views_for_models(
      self.tracks, lambda t: TrackView(t))
    for view in views:
      track_height = self.track_layout.size_of_item(view.track)
      x = self.x_of_time(0)
      w = self.x_of_time(view.track.duration) - x
      r = geom.Rectangle(
        x - 1, self.track_layout.position_of_item(view.track),
        w + 2, self.track_layout.size_of_track_view(view.track))
      r.y += round((track_height - r.height) / 2)
      view.size_allocate(r)
    self.back.size_allocate(geom.Rectangle(0, 0, width, height))
  # deselect when the user clicks
  def on_click(self, x, y, state):
    ViewManager.clear_selection()
    ViewManager.focused = None
    self.grab_focus()
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
      self.transport.add_observer(self.on_change)
    self.manager = manager
    if (manager):
      self.manager.add_observer(self.on_change)
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
      for track in self.tracks:
        r = geom.Rectangle(
          0, track_list_view.track_layout.position_of_item(track), 
          width, track_list_view.track_layout.size_of_item(track))
        if (track.arm):
          cr.set_source_rgba(1.0, 0.0, 0.0, 0.25 * fade)
          cr.rectangle(r.x, r.y, r.width, r.height)
          cr.fill()
        if (not track.enabled):
          cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.25 * fade)
          cr.rectangle(r.x, r.y, r.width, r.height)
          cr.fill()
    # draw transport state
    if (self.transport):
      # draw the transport's current time point with a fill on the left
      #  so we can easily see whether we're before or after it
      x = round(self.x_of_time(self.transport.time))
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

# display pitch names for a track
class PitchKeyView(LayoutView):
  def __init__(self, track, track_view):
    LayoutView.__init__(self, track)
    self.make_interactive()
    self._labels = dict()
    self._in_layout = False
    self.set_size_request(30, 80)
    self.entry = Gtk.Entry()
    self.entry.set_alignment(1.0)
    self.entry.connect('changed', self.on_edit)
    self.entry.connect('focus-out-event', self.on_end_edit)
    self._editing_pitch = None
    self.editable_area = geom.Rectangle()
    self.cursor_areas[self.editable_area] = Gdk.Cursor.new(
      Gdk.CursorType.XTERM)
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  # lay out the pitch labels
  def layout(self, width, height):
    self._in_layout = True
    # save old entries
    old_labels = dict(self._labels)
    # draw the pitch labels
    ty = 0
    if (self.track_view):
      ty = (height - self.track_view._height) / 2
      h = self.track_view.pitch_height
      for pitch in self.track.pitches:
        y = self.track_view.y_of_pitch(pitch)
        # make an entry widget for the pitch
        if (pitch in self._labels):
          label = self._labels[pitch]
          del old_labels[pitch]
        else:
          label = Gtk.Label()
          label.set_alignment(1.0, 0.5)
          self._labels[pitch] = label
          self.add(label)
        if (y is None): continue
        y = y + ty - math.floor(h / 2)
        name = self.track.name_of_pitch(pitch)
        label.set_text(name)
        r = geom.Rectangle(0, y, width, h)
        label.size_allocate(r)
        if (pitch == self._editing_pitch):
          self.entry.size_allocate(r)
      # remove unused entry widgets
      for (pitch, label) in old_labels.iteritems():
        label.destroy()
        del self._labels[pitch]
      # update the editable area
      self.editable_area.width = width
      self.editable_area.y = ty
      self.editable_area.height = self.track_view._height
    self._in_layout = False
  # activate the entry when a pitch is clicked
  def on_click(self, x, y, state):
    for (pitch, label) in self._labels.iteritems():
      r = label.get_allocation()
      if ((y >= r.y) and (y <= r.y + r.height)):
        if (self._editing_pitch is not None):
          self.on_end_edit()
        self.add(self.entry)
        self.entry.size_allocate(r)
        self.entry.set_text(self.track.name_of_pitch(pitch))
        self.entry.grab_focus()
        self._editing_pitch = pitch
  # respond to a text entry being edited
  def on_edit(self, *args):
    # update the track's pitch-to-name map
    if (self._editing_pitch is not None):
      ViewManager.begin_action(self.track, 1000)
      name = self.entry.get_text()
      if (len(name) > 0):
        self.track.pitch_names[self._editing_pitch] = name
      # if the user erases the pitch name, 
      #  revert to the default one
      elif (self._editing_pitch in self.track.pitch_names):
        del self.track.pitch_names[self._editing_pitch]
        self.track.on_change()
  # stop editing when the entry loses focus
  def on_end_edit(self, *args):
    if (self._editing_pitch is not None):
      self._editing_pitch = None
      self.remove(self.entry)

# display mixer controls for a track
class TrackMixerView(DrawableView):
  def __init__(self, track):
    DrawableView.__init__(self, track)
    self.make_interactive()
    self.level_rect = geom.Rectangle()
    self.pan_rect = geom.Rectangle()
    self.mute_rect = geom.Rectangle()
    self.solo_rect = geom.Rectangle()
    self.arm_rect = geom.Rectangle()
    self.handle_rect = geom.Rectangle()
    self.cursor_areas[self.pan_rect] = Gdk.Cursor.new(
      Gdk.CursorType.SB_H_DOUBLE_ARROW)
    self.cursor_areas[self.level_rect] = Gdk.Cursor.new(
      Gdk.CursorType.SB_V_DOUBLE_ARROW)
    self.cursor_areas[self.handle_rect] = Gdk.Cursor.new(
      Gdk.CursorType.SB_V_DOUBLE_ARROW)
    self._draggable_areas = ( self.level_rect, self.pan_rect )
    self._dragging_target = None
    self.set_size_request(60, 80)
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  # draw the mixer controls
  def redraw(self, cr, width, height):
    # get style
    style = self.get_style_context()
    fg = style.get_color(self.get_state())
    # allocate horizontal space
    handle_width = 8
    level_width = 20
    button_width = 20
    spacing = 4
    level_width = button_width = math.floor(
      (width - handle_width - (3 * spacing)) / 2)
    button_spacing = 4
    # draw the drag handle
    self.handle_rect.width = 8
    self.handle_rect.height = height
    x = 2
    w = handle_width - 4
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.2)
    cr.set_line_width(2)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    s = 5
    n = 5
    y = round((height / 2) - ((n / 2) * s))
    for i in range(0, n):
      cr.move_to(x, y)
      cr.line_to(x + w, y)
      cr.stroke()
      y += s
    cr.set_line_cap(cairo.LINE_CAP_BUTT)
    # place the pan/level bar
    x = handle_width + spacing
    self.pan_rect.x = x
    self.pan_rect.y = 0
    self.pan_rect.width = level_width
    self.pan_rect.height = math.ceil(level_width / 2) + spacing
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
    # draw the pan control
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
    cr.set_line_width(2)
    radius = (self.pan_rect.width / 2)
    cr.save()
    cr.translate(self.pan_rect.x + (self.pan_rect.width / 2),
                 self.pan_rect.y + self.pan_rect.height - spacing)
    cr.rotate(self.track.pan * (math.pi / 2))
    cr.move_to(0, - radius)
    cr.line_to(0, -1)
    cr.stroke()
    cr.move_to(0, 0)
    cr.line_to(-3, -4)
    cr.line_to(3, -4)
    cr.close_path()
    cr.fill()
    cr.restore()
    # draw the mixer bar
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
    cr.rectangle(self.level_rect.x, self.level_rect.y, 
                 self.level_rect.width, self.level_rect.height)
    cr.fill()
    h = max(2, round(self.level_rect.height * self.track.level))
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.15)
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
    self.draw_button(cr, self.solo_rect, 'S', fg, self.track.solo)
    self.draw_button(cr, self.mute_rect, 'M', fg, self.track.mute)
    self.draw_button(cr, self.arm_rect, 'R', fg, self.track.arm)
  # draw one of the track mode buttons
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
    
# display a header with general track information
class TrackHeaderView(Gtk.Box):
  def __init__(self, track, track_view):
    Gtk.Box.__init__(self)
    self.set_orientation(Gtk.Orientation.HORIZONTAL)
    self._track = track
    self._track_view = track_view
    self.mixer_view = TrackMixerView(self.track)
    self.pack_start(self.mixer_view, False, True, 0)
    self.pitch_key = PitchKeyView(self.track, track_view)
    self.pack_end(self.pitch_key, True, True, 0)
    ms = self.mixer_view.get_size_request()
    ps = self.pitch_key.get_size_request()
    self.set_size_request(ms[0] + ps[0], max(ms[1], ps[1]))
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._track)
  @property
  def track_view(self):
    return(self._track_view)
  @track_view.setter
  def track_view(self, value):
    self._track_view = value
    self.pitch_key.track_view = value
  # do layout
  def layout(self, width, height):
    w = 60
    self.mixer_view.size_allocate(geom.Rectangle(0, 0, w, height))
    self.pitch_key.size_allocate(geom.Rectangle(w, 0, width - w, height))
    
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
  # place tracks in the view
  def layout(self, width, height):
    views = self.allocate_views_for_models(
      self.tracks, 
      lambda t: TrackHeaderView(t, None))
    for view in views:
      view.track_view = ViewManager.view_for_model(view.track, TrackView)
      view.size_allocate(geom.Rectangle(
        0, self.track_layout.position_of_item(view.track),
        width, self.track_layout.size_of_item(view.track)))
      size = view.get_size_request()
