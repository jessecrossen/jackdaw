import math
import cairo

from gi.repository import Gtk, Gdk

import geom
import symbols
from core import DrawableView, LayoutView, ViewManager, ListLayout, TimeScale
import block

class TrackView(LayoutView):
  def __init__(self, track, time_scale):
    LayoutView.__init__(self, track)
    self.make_transparent()
    self.make_interactive()
    self.time_scale = time_scale
    self.time_scale.add_observer(self.on_change)
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
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
    views = self.allocate_views_for_models(
      self.track, lambda b: block.BlockView(b, self.time_scale))
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
    header_view = ViewManager.view_for_model(self.track, PitchKeyView)
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
  def __init__(self, tracks, transport=None, track_layout=None, 
                     time_scale=None):
    LayoutView.__init__(self, tracks)
    self.track_layout = track_layout
    if (self.track_layout is None):
      self.track_layout = TrackLayout(self.tracks)
    if (time_scale is None):
      time_scale = TimeScale()
    self.time_scale = time_scale
    self.time_scale.add_observer(self.on_change)
    # make a background view
    self.back = TrackListBackgroundView(self.tracks, self.time_scale,
                                        transport=transport, 
                                        manager=ViewManager)
    self.add(self.back)
    # receive events
    self.make_interactive()
    # set up scrolling
    self.time_scroll = Gtk.Adjustment()
    self.time_scroll.connect('value-changed', self.on_scroll)
    self.time_scroll.set_lower(0.0)
    self.time_scroll.set_value(0.0)
    self.time_scroll.set_step_increment(1.0)
  def on_scroll(self, *args):
    self.on_change()
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
  # map between track index and position
  def y_of_track_index(self, index):
    try:
      return(self.track_layout.position_of_item(self.tracks[index]))
    except IndexError:
      return(None)
  # place tracks in the view
  def layout(self, width, height):
    # get the duration of the longest track
    max_duration = 0
    for track in self.tracks:
      max_duration = max(max_duration, track.duration)
    # update horizontal scrolling
    page_duration = min(max_duration, self.time_scale.time_of_x(width))
    self.time_scroll.set_upper(max_duration)
    self.time_scroll.set_page_size(page_duration)
    self.time_scroll.set_page_increment(page_duration * 0.9)
    self.time_scroll.changed()
    left_time = self.time_scroll.get_value()
    clamped = min(max(0.0, left_time), max_duration - page_duration)
    if (clamped != left_time):
      left_time = clamped
      self.time_scroll.set_value(left_time)
    # do layout for track views
    views = self.allocate_views_for_models(
      self.tracks, lambda t: TrackView(t, self.time_scale))
    x = self.x_of_time(0) - self.time_scale.x_of_time(left_time)
    for view in views:
      track_height = self.track_layout.size_of_item(view.track)
      w = self.time_scale.x_of_time(view.track.duration)
      r = geom.Rectangle(
        x - 1, self.track_layout.position_of_item(view.track),
        w + 2, self.track_layout.size_of_track_view(view.track))
      r.y += round((track_height - r.height) / 2)
      view.size_allocate(r)
    w = self.time_scale.x_of_time(max_duration)
    self.back.size_allocate(geom.Rectangle(x - 1, 0, w + 2, height))
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
  def __init__(self, tracks, time_scale, transport=None, manager=None):
    DrawableView.__init__(self, tracks)
    self.transport = transport
    if (transport):
      self.transport.add_observer(self.on_change)
    self.manager = manager
    if (manager):
      self.manager.add_observer(self.on_change)
    self.time_scale = time_scale
    self.time_scale.add_observer(self.on_change)
  # expose 'tracks' as an alternate name for 'model'
  @property
  def tracks(self):
    return(self._model)
  def x_of_time(self, time):
    return(1 + self.time_scale.x_of_time(time))
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
  def __init__(self, track):
    LayoutView.__init__(self, track)
    self.make_interactive()
    self._labels = dict()
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
    # get a view for the track that has pitches
    track_view = ViewManager.view_for_model(self._model, TrackView)
    # save old entries
    old_labels = dict(self._labels)
    # draw the pitch labels
    ty = 0
    if (track_view):
      ty = (height - track_view._height) / 2
      h = track_view.pitch_height
      max_width = 0
      for pitch in self.track.pitches:
        y = track_view.y_of_pitch(pitch)
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
        (minimum_size, preferred_size) = label.get_preferred_size()
        max_width = max(max_width, preferred_size.width)
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
      self.editable_area.height = track_view._height
      # request the size of the widest label
      self.set_size_request(max_width + 12, -1)
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

# display a view to indicate and control whether a track is armed
class TrackArmView(DrawableView):
  def __init__(self, track):
    DrawableView.__init__(self, track)
    self.make_interactive()
  @property
  def track(self):
    return(self._model)
  def redraw(self, cr, width, height):
    y = round(height / 2.0)
    p1 = geom.Point(0, y)
    p2 = geom.Point(width, y)
    if (self.track.arm):
      s = '1'
    else:
      s = '0' 
    symbols.draw_path(cr, (p1, p2), s)
  def on_click(self, x, y, state):
    self.track.arm = not self.track.arm
    
# a view that makes a transition between tracks or inputs and the signal path
class TransitionView(DrawableView):
  def __init__(self, model, style):
    DrawableView.__init__(self, model)
    self.style = style
  def redraw(self, cr, width, height):
    y = round(height / 2)
    p1 = geom.Point(0, y)
    p2 = geom.Point(width, y)
    if (self.style[0] in '}])'):
      p1.x += (symbols.BRACKET_WIDTH + 2)
    elif (self.style[-1] in '{[('):
      p2.x -= (symbols.BRACKET_WIDTH + 2)
    elif (self.style[0] in 'o*x<'):
      p1.x += (symbols.RADIUS * 2)
    elif (self.style[-1] in 'o*x>'):
      p2.x -= (symbols.RADIUS * 2)
    symbols.draw_path(cr, (p1, p2), self.style)
class FromSignalTransitionView(TransitionView):
  def __init__(self, model):
    TransitionView.__init__(self, model, '->')
class ToSignalTransitionView(TransitionView):
  def __init__(self, model):
    TransitionView.__init__(self, model, '>-')

# display mute and solo controls for a track
class TrackMuteSoloView(DrawableView):
  def __init__(self, track):
    DrawableView.__init__(self, track)
    self.make_interactive()
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  def redraw(self, cr, width, height):
    y = round(height / 2)
    lx = (symbols.RADIUS * 2)
    rx = (width - lx)
    sy = y - (symbols.RADIUS * 6)
    # draw the solo label
    cr.set_font_size(8.0)
    (xb, yb, w, h, xa, ya) = cr.text_extents('SOLO')
    cr.move_to(((lx + rx) / 2) - (w / 2) - xb, sy - yb + symbols.RADIUS)
    cr.show_text('SOLO')
    # lay out the switches on center
    inset = math.floor((width - 20) / 2)
    # draw the mute switch
    symbols.draw_path(cr, 
      (geom.Point(0, y), geom.Point(lx, y), 
       geom.Point(rx, y), geom.Point(width, y)),
      '-'+('0' if self.track.mute else '1')+'-')
    # draw the solo switch
    symbols.draw_path(cr, 
      (geom.Point(lx, y), geom.Point(lx, sy),
       geom.Point(rx, sy), geom.Point(rx, y)),
      '.-.'+('1' if self.track.solo else '0')+'.-.')
  # toggle mute/solo on click
  def on_click(self, x, y, state):
    dy = (self._height / 2) - (symbols.RADIUS * 3)
    if (y < dy):
      self.track.solo = not self.track.solo
    else:
      self.track.mute = not self.track.mute

# display mixer controls for a track
class TrackMixerView(DrawableView):
  def __init__(self, track):
    DrawableView.__init__(self, track)
    self.make_interactive()
    self.enable_automation = True
    self.bar_area = geom.Rectangle()
  # expose 'track' as an alternate name for 'model' for readability
  @property
  def track(self):
    return(self._model)
  # draw the mixer controls
  def redraw(self, cr, width, height):
    left = self.track.level
    right = self.track.level
    if (self.track.pan < 0.0):
      right *= (1.0 - abs(self.track.pan))
    elif (self.track.pan > 0.0):
      left *= (1.0 - abs(self.track.pan))
    # inset on the left and bottom so we can show connections
    bars = self.bar_area
    bars.x = 1; bars.y = 1
    bars.width = width - 2
    bars.height = height - 2
    if (self.enable_automation):
      inset = symbols.RADIUS * 4
      bars.x += inset
      bars.width -= inset
      bars.height -= inset
    else:
      inset = symbols.RADIUS
      bars.x += inset; bars.y += inset
      bars.width -= inset; bars.height -= inset
    lb = geom.Rectangle(bars.x, bars.y, 
      round(bars.width / 2), bars.height)
    rb = geom.Rectangle(lb.x + lb.width, bars.y,
      bars.width - lb.width, bars.height)
    lh = round(lb.height * left)
    rh = round(rb.height * right)
    lb.y += lb.height - lh
    lb.height = lh
    rb.y += rb.height - rh
    rb.height = rh
    # draw the inner level bars
    cr.save()
    (r, g, b, a) = cr.get_source().get_rgba()
    cr.set_source_rgba(r, g, b, 0.25)
    cr.rectangle(lb.x, lb.y, lb.width, lb.height)
    cr.rectangle(rb.x, rb.y, rb.width, rb.height)
    cr.fill()
    cr.restore()
    # draw an outline around them
    cr.set_line_width(2)
    symbols.draw_round_rect(cr, bars.x, bars.y, bars.width, bars.height, 2)
    cr.stroke()
    # draw the pan direction indicator
    rad = round(bars.width / 2.0)
    cr.save()
    cr.set_source_rgba(r, g, b, 0.5)
    cr.translate(bars.x + rad, bars.y + bars.height - 4)
    cr.rotate(self.track.pan * (math.pi / 2))
    cr.move_to(0, -rad)
    cr.line_to(0, -6)
    cr.stroke()
    cr.move_to(0, 0)
    cr.line_to(-3, -6)
    cr.line_to(3, -6)
    cr.close_path()
    cr.fill()
    cr.restore()
    # draw connections for the level and pan if automation is on
    if (self.enable_automation):
      rad = symbols.RADIUS
      y = bars.y + bars.height - (rad * 2)
      symbols.draw_path(cr, 
        (geom.Point(bars.x, y), geom.Point(rad, y)), 
        '-o')
      x = bars.x + round(bars.width / 2.0)
      y = bars.y + bars.height + (rad * 2) 
      symbols.draw_path(cr, 
        (geom.Point(x, bars.y + bars.height), geom.Point(x, y), 
         geom.Point(rad, y)), 
        '-.-o')
    # draw a connection showing the incoming track signal
    y = round(height / 2.0)
    symbols.draw_path(cr, 
      (geom.Point(0, y), geom.Point(bars.x, y)), 
      '-')
  # handle drag and drop
  def start_drag(self, x, y, state):
    if (self.bar_area.contains(x, y)):
      self._drag_level = None
      self._drag_pan = None 
      return(True)
  def on_drag(self, dx, dy, state):
    if (self._drag_level is not None):
      self.track.level = self._drag_level - (dy / self._height)
    elif (self._drag_pan is not None):
      self.track.pan = self._drag_pan + (dx / self._width)
    elif (abs(dx - dy) > 6):
      ViewManager.begin_action((self.track,))
      if (dx > dy):
        self._drag_pan = self.track.pan
      else:
        self._drag_level = self.track.level
  def on_drop(self):
    if ((self._drag_level is not None) or 
        (self._drag_pan is not None)):
      ViewManager.end_action()
    self._drag_level = None
    self._drag_pan = None
    
