import math

from PySide.QtCore import *
from PySide.QtGui import *

from ..common import observable
import core
from ..models.core import Selection
from ..models.doc import ViewScale

# represent a block of events on a track
class BlockView(core.BoxSelectable, core.TimeDraggable, core.ModelView):
  def __init__(self, block, track=None, parent=None):
    core.ModelView.__init__(self, block, parent)
    core.TimeDraggable.__init__(self)
    core.BoxSelectable.__init__(self)
    self._track = track
    self.note_layouts = list()
    self.repeat_view = BlockRepeatView(self.block.repeat, self)
    self.start_view = BlockStartView(self.block.start, self)
    self.end_view = BlockEndView(self.block.end, self)
    # enable clipping to hide partial repeats
    self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
  @property
  def block(self):
    return(self._model)
  @property
  def track(self):
    return(self._track)
  # do background drawing and layout
  def layout(self):
    r = self.rect()
    width = r.width()
    height = r.height()
    # add note layouts to cover the duration of the block
    duration = float(self.block.duration)
    repeat_time = float(self.block.events.duration)
    repeats = max(1, int(math.ceil(duration / repeat_time)))
    for i in range(0, repeats):
      if (i < len(self.note_layouts)):
        layout = self.note_layouts[i]
        layout.items = self.block.events
      else:
        layout = NoteLayout(self, self.block.events, self.track)
        self.note_layouts.append(layout)
      layout.setPos(QPointF(i * repeat_time, 0.0))
    # remove extraneous layouts
    for i in range(repeats, len(self.note_layouts)):
      layout = self.note_layouts.pop()
      layout.destroy()
    # place the block's placeholders
    self.start_view.setRect(QRectF(0.0, 0.0, 0.0, height))
    self.repeat_view.setRect(QRectF(repeat_time, 0.0, 0.0, height))
    self.end_view.setRect(QRectF(duration, 0.0, 0.0, height))
  def paint(self, qp, options, widget):
    r = self.rect()
    width = r.width()
    height = r.height()
    # choose a color for the background
    selected = self.block.selected
    if (selected):
      qp.setBrush(self.palette.brush(
        QPalette.Normal, QPalette.Highlight))
    else:
      qp.setBrush(QBrush(self.palette.color(QPalette.Normal, QPalette.Base)))
    qp.setPen(Qt.NoPen)
    qp.drawRect(QRectF(0, 0, width, height))
    # draw lines for divisions, if there are any
    color = self.palette.color(QPalette.Normal, QPalette.WindowText)
    color.setAlphaF(0.10)
    qp.setPen(QPen(color))
    events = self.block.events
    if (events.divisions > 1):
      div_time = float(events.duration) / float(events.divisions)
      # if the space between divisions is too small, don't show them
      t = div_time
      while ((div_time > 0) and (t < self.block.duration)):
        qp.drawLine(QPointF(t, 0), QPointF(t, height))
        t += div_time
  # show a context menu with block actions
  def contextMenuEvent(self, e):
    # walk up the chain to find the track list this block is being 
    #  presented in, falling back to just the block's track
    node = self
    tracks = (self.track,)
    while(node):
      if (hasattr(node, 'tracks')):
        tracks = node.tracks
        break
      node = node.parentItem()
    # create and show the menu
    menu = BlockMenu(parent=e.widget(),
                     block=self.block, 
                     tracks=tracks)
    menu.popup(e.screenPos())

# do layout for notes in a block
class NoteLayout(core.ListLayout):
  def __init__(self, parent, notes, track):
    self._track = track
    self._track.add_observer(self.layout)
    core.ListLayout.__init__(self, parent, notes, self.note_view_for_event)
  def note_view_for_event(self, event):
    try:
      p = event.pitch
    except AttributeError:
      return(None)
    return(NoteView(event))
  def layout(self):
    pitch_map = dict()
    i = 0.0
    for pitch in reversed(self._track.pitches):
      pitch_map[pitch] = i
      i += 1.0
    for view in self._views:
      note = view.note
      try:
        y = pitch_map[note.pitch]
      except KeyError:
        y = -1.0
      view.setRect(QRectF(note.time, y, note.duration, 1.0))

# represent a note event in a block
class NoteView(core.TimeDraggable, core.PitchDraggable, core.ModelView):
  RADIUS = 2.0
  def __init__(self, note, parent=None):
    core.ModelView.__init__(self, note, parent)
    core.TimeDraggable.__init__(self)
    core.PitchDraggable.__init__(self)
  @property
  def note(self):
    return(self._model)
  # ensure the note always has some width
  def rect(self):
    r = core.ModelView.rect(self)
    if (r.width() < 0.001):
      r.setWidth(0.001)
    sr = self.mapRectToScene(r)
    min_width = sr.height() / 2.0
    if (sr.width() < min_width):
      r.setWidth(min_width * (r.width() / sr.width()))
    return(r)
  def paint(self, qp, options, widget):
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
    qp.setPen(Qt.NoPen)
    r = self.rect()
    width = r.width()
    height = r.height()
    t = qp.deviceTransform()
    rx = self.RADIUS / t.m11()
    ry = self.RADIUS / t.m22()
    qp.drawRoundedRect(QRectF(0.0, 0.0, width, height), rx, ry)

# represent the start of a block
class BlockStartView(core.TimeDraggable, core.ModelView):
  WIDTH = 6.0
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, self.WIDTH, 0.0))
    return(QRectF(0.0, 0.0, r.width(), self.rect().height()))
  def paint(self, qp, options, widget):
    qp.setBrush(self.brush())
    qp.setPen(Qt.NoPen)
    t = qp.deviceTransform()
    px = 1.0 / t.m11()
    py = 1.0 / t.m22()
    w = self.WIDTH * px
    h = self.rect().height()
    qp.drawPolygon(QPolygonF([
      QPointF(0.0, 0.0), QPointF(w, 0.0),
      QPointF(w, 1.0 * py), QPointF(2.0 * px, 2.0 * py),
      QPointF(2.0 * px, h - (2.0 * py)), QPointF(w, h - py),
      QPointF(w, h), QPointF(0.0, h)
    ]))
# represent the end of a block
class BlockEndView(core.TimeDraggable, core.ModelView):
  WIDTH = 6.0
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, self.WIDTH, 0.0))
    return(QRectF(- r.width(), 0.0, r.width(), self.rect().height()))
  def paint(self, qp, options, widget):
    qp.setBrush(self.brush())
    qp.setPen(Qt.NoPen)
    t = qp.deviceTransform()
    px = 1.0 / t.m11()
    py = 1.0 / t.m22()
    x = - (self.WIDTH * px)
    h = self.rect().height()
    qp.drawPolygon(QPolygonF([
      QPointF(x, 0.0), QPointF(0.0, 0.0),
      QPointF(0.0, h), QPointF(x, h),
      QPointF(x, h - py), QPointF(-(2.0 * px), h - (2.0 * py)),
      QPointF(- (2.0 * px), 2.0 * py), QPointF(x, 1.0 * py)
    ]))
# represent the repeat length of a block
class BlockRepeatView(core.TimeDraggable, core.ModelView):
  WIDTH = 12.0
  def __init__(self, model, parent=None):
    core.ModelView.__init__(self, model, parent)
    core.TimeDraggable.__init__(self)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, 1.0, 0.0))
    px = r.width()
    return(QRectF(- ((self.WIDTH - 1) * px), 0.0, 
      self.WIDTH * px, self.rect().height()))
  def paint(self, qp, options, width):
    qp.setBrush(self.brush(0.25))
    qp.setPen(Qt.NoPen)
    t = qp.deviceTransform()
    px = 1.0 / t.m11()
    py = 1.0 / t.m22()
    h = self.rect().height()
    qp.drawRect(QRectF(-1.0 * px, 0.0, 2.0 * px, h))
    qp.drawRect(QRectF(- (4.0 * px), 0.0, 2.0 * px, h))
    x = - (8.0 * px)
    y = round(h / 2)
    r = 1.5
    qp.drawEllipse(QPointF(x, y - 0.5), r * px, r * py)
    qp.drawEllipse(QPointF(x, y + 0.5), r * px, r * py)

class BlockMenu(QMenu):
  def __init__(self, block, tracks, parent=None):
    QMenu.__init__(self, parent)
    self.block = block
    self.tracks = tracks
    split_action = QAction('Split', self)
    split_action.setStatusTip('Split the block into multiple blocks')
    split_action.triggered.connect(self.on_split)
    join_action = QAction('Join', self)
    join_action.setStatusTip('Join selected blocks into one')
    join_action.triggered.connect(self.on_join)
    self.addAction(split_action)
    self.addAction(join_action)
    # disable actions that can't be performed
    # get all the selected blocks
    selected = self.get_selected_blocks()
    # if the block is the only one selected, it can be split
    split_action.setEnabled((len(selected) == 0) or 
      ((len(selected) == 1) and (self.block in selected)))
    # if more than one block is selected, they can be joined
    join_action.setEnabled(
      (len(selected) == 0) or (self.block in selected))
  # get all blocks in the selection
  def get_selected_blocks(self):
    blocks = set()
    for item in Selection.models:
      if (hasattr(item, 'events')):
        blocks.add(item)
    return(blocks)
  # get selected events within the current block
  def get_selected_notes(self):
    block_events = set(self.block.events)
    selected_events = set()
    for item in Selection.models:
      if ((item in block_events) and (hasattr(item, 'pitch'))):
        selected_events.add(item)
    return(selected_events)
  # join multiple blocks
  def on_join(self, *args):
    blocks = self.get_selected_blocks()
    blocks.add(self.block)
    core.ViewManager.begin_action((blocks, self.tracks))
    if (len(blocks) > 1):
      self.block.join(blocks, tracks=self.tracks)
    else:
      self.block.join_repeats()
    core.ViewManager.end_action()
  # split a block at selected note boundaries
  def on_split(self, *args):
    current_track = None
    for track in self.tracks:
      if (self.block in track):
        current_track = track
        break
    # if the block has multiple repeats, split the repeats
    if (self.block.events.duration < self.block.duration):
      core.ViewManager.begin_action(track)
      self.block.split_repeats(track=current_track)
      core.ViewManager.end_action()
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
        core.ViewManager.begin_action((self.block, current_track))
        self.block.split(times, track=current_track)
        core.ViewManager.end_action()


