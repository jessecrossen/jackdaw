import math

from PySide.QtCore import *
from PySide.QtGui import *

from ..common import observable
# import symbols
import core
from ..models.doc import ViewScale

# make a mixin for laying out timed elements using a view scale
class TimedLayout(object):
  def __init__(self, view_scale, margin=None):
    self.view_scale = view_scale
    self.view_scale.add_observer(self.invalidate)
    self._margin = margin if (margin is not None) else 1
  def destroy(self):
    self.view_scale.remove_observer(self.invalidate)
  # get the x coordinate for a given time
  def x_of_time(self, time):
    try:
      return(self._margin + self.view_scale.x_of_time(time))
    except ZeroDivisionError:
      return(0)

# do layout for events in a block
class EventsLayout(TimedLayout, core.ModelListLayout):
  def __init__(self, events, view_scale, pitch_source=None, margin=None):
    core.ModelListLayout.__init__(self, events)
    TimedLayout.__init__(self, view_scale, margin)
    self._pitch_source = None
    self.set_pitch_source(pitch_source)
  def destroy(self):  
    if (self._pitch_source):
      self._pitch_source.remove_observer(self.on_change)
    core.ModelListLayout.destroy(self)
    TimedLayout.destroy(self)
  @property
  def events(self):
    return(self._model_list)
  # suggest a size for the events
  def sizeHint(self):
    return(self.minimumSize())
  def minimumSize(self):
    return(QSize(
      self.view_scale.x_of_time(self.events.duration + (2 * self._margin)),
      len(self.pitches) * self.view_scale.pitch_height))
  # the list of pitches to display can be sourced from the event list 
  #  or can be set externally, as when displayed as part of a track
  @property
  def pitches(self):
    if (self._pitch_source != None):
      return(self._pitch_source.pitches)
    return(self.events.pitches)
  def set_pitch_source(self, value):
    if (self._pitch_source != value):
      if (self._pitch_source):
        self._pitch_source.remove_observer(self.on_change)
      self._pitch_source = value
      if (self._pitch_source):
        self._pitch_source.add_observer(self.on_change)
      self.on_change()
  # get a view for the given event
  def get_view_for_model(self, model):
    return(NoteView(model))
  # lay out events by time and duration
  def do_layout(self):
    rect = self.geometry()
    # map pitches to coordinates for fast lookup
    pitch_height = self.view_scale.pitch_height
    y_of_pitch = dict()
    i = 0
    for pitch in reversed(self.pitches):
      y_of_pitch[pitch] = i * pitch_height
      i += 1
    for view in self.views:
      model = view.model
      try:
        y = y_of_pitch[model.pitch]
      except IndexError: continue
      x1 = rect.x() + self.x_of_time(model.time)
      x2 = rect.x() + self.x_of_time(model.time + model.duration)
      # give the note a minimum width
      w = max(NoteView.RADIUS * 2, x2 - x1)
      w = max(pitch_height / 2, w)
      view.setGeometry(QRect(x1, y, w, pitch_height))

# do layout for a block's start, end, and repeat points
class BlockPlaceholderLayout(TimedLayout, core.ListLayout):
  CAP_WIDTH = 10
  REPEAT_WIDTH = 12
  def __init__(self, block, view_scale, margin=None):
    core.ListLayout.__init__(self)
    TimedLayout.__init__(self, view_scale, margin)
    self.block = block
    self.repeat_view = BlockRepeatView(block.repeat)
    block.repeat.add_observer(self.invalidate)
    self.start_view = BlockStartView(block.start)
    self.end_view = BlockEndView(block.end)
    self.addWidget(self.repeat_view)
    self.addWidget(self.start_view)
    self.addWidget(self.end_view)
  def destroy(self):
    self.repeat.remove_observer(self.invalidate)
    core.ListLayout.destroy(self)
    TimedLayout.destroy(self)
  def setGeometry(self, rect):
    QLayout.setGeometry(self, rect)
    self.do_layout()
  def do_layout(self):
    r = self.geometry()
    self.start_view.setGeometry(QRect(
      r.x(), r.y(), self.CAP_WIDTH, r.height()))
    self.end_view.setGeometry(QRect(
      r.right() - self.CAP_WIDTH + 1, r.y(), self.CAP_WIDTH, r.height()))
    x = self.x_of_time(self.repeat_view.model.time) + 1
    self.repeat_view.setGeometry(QRect(
      x - self.REPEAT_WIDTH, r.y(), self.REPEAT_WIDTH, r.height()))
    self.repeat_view.setVisible(x < r.width() - 1)

# do layout of the multiple repeats in a block
class BlockRepeatLayout(TimedLayout, core.ListLayout):
  def __init__(self, block, view_scale, track=None, margin=None):
    core.ListLayout.__init__(self)
    TimedLayout.__init__(self, view_scale, margin)
    self._block = block
    self._track = track
    self.block.add_observer(self.update_repeats)
    self.update_repeats()
  def destroy(self):
    self.block.remove_observer(self.update_repeats)
    core.ListLayout.destroy(self)
    TimedLayout.destroy(self)
  @property
  def block(self):
    return(self._block)
  # make sure we have the right number of repeats to cover the block
  def update_repeats(self):
    repeats = max(1, int(
      math.ceil(self.block.duration / self.block.events.duration)))
    while(len(self._items) < repeats):
      self.addLayout(EventsLayout(self.block.events, 
        view_scale=self.view_scale, 
        pitch_source=self._track,
        margin=0))
    while(len(self._items) > repeats + 1):
      removed = self.takeAt(self.count() - 1)
      removed.destroy()
  def setGeometry(self, rect):
    QLayout.setGeometry(self, rect)
    self.do_layout()
  def do_layout(self):
    r = self.geometry()
    time = 0.0
    duration = self.block.events.duration
    for item in self._items:
      item.setGeometry(QRect(self.x_of_time(time), r.y(), 
        self.view_scale.x_of_time(duration), r.height()))
      time += duration

# represent a block of events on a track
class BlockView(core.TimeDraggable, core.ModelView):
  def __init__(self, block, view_scale, track=None, parent=None, margin=1):
    core.ModelView.__init__(self, block, parent)
    core.TimeDraggable.__init__(self)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
    self._track = track
    self._margin = margin
    # make a master layout
    self.layout = core.OverlayLayout()
    # add a layout for the block's events
    self.repeat_layout = BlockRepeatLayout(self.block, 
      track=track,
      view_scale=self.view_scale,
      margin=self._margin)
    self.layout.addLayout(self.repeat_layout)
    # add a layout for the block's start, end, and repeat length
    self.placeholder_layout = BlockPlaceholderLayout(self.block, 
      view_scale=self.view_scale,
      margin=self._margin)
    self.layout.addLayout(self.placeholder_layout)
    # activate the layout
    self.setLayout(self.layout)
  def destroy(self):
    self.view_scale.remove_observer(self.on_change)
    core.ModelView.destroy(self)
  @property
  def block(self):
    return(self._model)
  @property
  def track(self):
    return(self._track)
  def redraw(self, qp, width, height):
    selected = self.block.selected
    if (selected):
      qp.setBrush(self.palette.brush(
        QPalette.Normal, QPalette.Highlight))
    else:
      qp.setBrush(QBrush(self.palette.color(QPalette.Normal, QPalette.Base)))
    qp.drawRect(0, 0, width, height)
    # draw lines for divisions, if there are any
    color = self.palette.color(QPalette.Normal, QPalette.WindowText)
    color.setAlphaF(0.05)
    qp.setPen(QPen(color))
    events = self.block.events
    if (events.divisions > 1):
      div_time = float(events.duration) / float(events.divisions)
      # if the space between divisions is too small, don't show them
      if (self.view_scale.x_of_time(div_time) >= 4):
        t = 0.0
        while ((div_time > 0) and (t < self.block.duration)):
          t += div_time
          x = self._margin + round(self.view_scale.x_of_time(t))
          qp.drawLine(x, 0, x, height)

# represent a note event in a block
class NoteView(core.TimeDraggable, core.PitchDraggable, core.ModelView):
  RADIUS = 2
  def __init__(self, note, parent=None):
    core.ModelView.__init__(self, note, parent)
    core.TimeDraggable.__init__(self)
    core.PitchDraggable.__init__(self)
  @property
  def note(self):
    return(self._model)
  def redraw(self, qp, width, height):
    selected = self.note.selected
    role = QPalette.Highlight if selected else QPalette.WindowText
    color = self.palette.color(QPalette.Normal, role)
    # dim notes to show velocity
    velocity = 1.0
    try:
      velocity = self.note.velocity
    except AttributeError: pass
    if (velocity < 1.0):
      color.setAlphaF(0.1 + (0.9 * velocity))
    qp.setBrush(QBrush(color))
    qp.drawRoundedRect(0, 0, width, height, self.RADIUS, self.RADIUS)

# represent the start of a block
class BlockStartView(core.TimeDraggable, core.ModelView):
  WIDTH = 6
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def redraw(self, qp, width, height):
    qp.setBrush(self.brush())
    w = min(self.WIDTH, width)
    qp.drawPolygon(QPolygon([
      QPoint(0, 0), QPoint(w, 0),
      QPoint(w, 1), QPoint(2, 2),
      QPoint(2, height - 2), QPoint(w, height - 1),
      QPoint(w, height), QPoint(0, height)
    ]))
# represent the end of a block
class BlockEndView(core.TimeDraggable, core.ModelView):
  WIDTH = 6
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def redraw(self, qp, width, height):
    qp.setBrush(self.brush())
    w = min(self.WIDTH, width)
    x = width - w
    qp.drawPolygon(QPolygon([
      QPoint(x, 0), QPoint(width, 0),
      QPoint(width, height), QPoint(x, height),
      QPoint(x, height - 1), QPoint(width - 2, height - 2),
      QPoint(width - 2, 2), QPoint(x, 1)
    ]))
# represent the repeat length of a block
class BlockRepeatView(core.TimeDraggable, core.ModelView):
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def redraw(self, qp, width, height):
    qp.setBrush(self.brush(0.25))
    qp.drawRect(width - 2, 0, 2, height)
    qp.drawRect(width - 5, 0, 2, height)
    x = width - 9
    y = round(height / 2)
    r = 1.5
    qp.drawEllipse(QPointF(x, y - 5), r, r)
    qp.drawEllipse(QPointF(x, y + 5), r, r)

## make a context menu for blocks
#class BlockMenu(ContextMenu):
#  def __init__(self, block, tracks=None):
#    ContextMenu.__init__(self, block)
#    self.tracks = tracks
#    # add menu items
#    self.join_item = self.make_item('Join', self.on_join)
#    self.split_item = self.make_item('Split', self.on_split)
#    self.show_all()
#  @property
#  def block(self):
#    return(self._model)
#  def on_change(self):
#    # get all the selected blocks
#    selected = self.get_selected_blocks()
#    # if the block is the only one selected it can be split
#    self.split_item.set_sensitive((len(selected) == 0) or 
#      ((len(selected) == 1) and (self.block in selected)))
#    # if more than one block is selected, they can be joined
#    self.join_item.set_sensitive(
#      (len(selected) == 0) or (self.block in selected))
#  # get all blocks in the selection
#  def get_selected_blocks(self):
#    blocks = set()
#    for item in ViewManager.selection:
#      if (hasattr(item, 'events')):
#        blocks.add(item)
#    return(blocks)
#  # get selected events within the current block
#  def get_selected_notes(self):
#    block_events = set(self.block.events)
#    selected_events = set()
#    for item in ViewManager.selection:
#      if ((item in block_events) and (hasattr(item, 'pitch'))):
#        selected_events.add(item)
#    return(selected_events)
#  # join multiple blocks
#  def on_join(self, *args):
#    blocks = self.get_selected_blocks()
#    blocks.add(self.block)
#    ViewManager.begin_action((blocks, self.tracks))
#    if (len(blocks) > 1):
#      self.block.join(blocks, tracks=self.tracks)
#    else:
#      self.block.join_repeats()
#    ViewManager.end_action()
#  # split a block at selected note boundaries
#  def on_split(self, *args):
#    # find the track this block is in so we can place 
#    #  the new split-off blocks somewhere
#    track = None
#    if (self.tracks):
#      for search_track in self.tracks:
#        if (self.block in search_track):
#          track = search_track
#          break
#    if (track is None): return
#    # if the block has multiple repeats, split the repeats
#    if (self.block.events.duration < self.block.duration):
#      ViewManager.begin_action(track)
#      self.block.split_repeats(track=track)
#      ViewManager.end_action()
#    else:
#      times = [ ]
#      # get selected events in the block
#      selected_events = self.get_selected_notes()
#      # if events are selected in the block, find boundaries 
#      #  between selected and deselected events
#      if (len(selected_events) > 0):
#        # sort all block events by time
#        events = list(self.block.events)
#        events.sort(key=lambda e: e.time)
#        # find boundaries
#        was_selected = (events[0] in selected_events)
#        for event in events:
#          # count notes only
#          if (not hasattr(event, 'pitch')): continue
#          is_selected = (event in selected_events)
#          if (is_selected != was_selected):
#            times.append(event.time)
#            was_selected = is_selected
#      # if there are times to split on, we can split
#      if (len(times) > 0):
#        ViewManager.begin_action((self.block, track))
#        self.block.split(times, track=track)
#        ViewManager.end_action()
