import math

from PySide.QtCore import *
from PySide.QtGui import *

import observable
import view
from doc import ViewScale

# represent a block of events on a track
class BlockView(view.BoxSelectable, view.TimeDraggable, view.Deleteable, view.ModelView):
  def __init__(self, block, track=None, parent=None):
    view.ModelView.__init__(self, block, parent)
    view.Deleteable.__init__(self)
    view.TimeDraggable.__init__(self)
    view.BoxSelectable.__init__(self)
    self._track = track
    self.note_layouts = list()
    self.repeat_view = BlockRepeatView(self.block.repeat, self)
    self.start_view = BlockStartView(self.block.start, self)
    self.end_view = BlockEndView(self.block.end, self)
    self.controller_layout = ControllerLayout(self, self.block.events, self.track)
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
    pitch_height = float(len(self.track.pitches))
    # add note layouts to cover the duration of the block
    duration = float(self.block.duration)
    repeat_time = float(self.block.events.duration)
    repeats = max(1, int(math.ceil(duration / repeat_time)))
    for i in range(0, repeats):
      if (i < len(self.note_layouts)):
        layout = self.note_layouts[i]
        layout.items = self.block.events.notes
      else:
        layout = NoteLayout(self, self.block.events.notes, self.track)
        self.note_layouts.append(layout)
      layout.setRect(QRectF(i * repeat_time, 0.0, repeat_time, pitch_height))
    # remove extraneous layouts
    for i in range(repeats, len(self.note_layouts)):
      layout = self.note_layouts.pop()
      layout.destroy()
    # place controllers below pitches
    self.controller_layout.setRect(QRectF(0.0, pitch_height, 
                                          width, height - pitch_height))
    # place the block's placeholders
    self.start_view.setRect(QRectF(0.0, 0.0, 0.0, height))
    self.repeat_view.setRect(QRectF(repeat_time, 0.0, 0.0, height))
    self.end_view.setRect(QRectF(duration, 0.0, 0.0, height))
  def clipRect(self):
    return(self.boundingRect())  
  def _paint(self, qp):
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

# do layout for control changes in a block
class ControllerLayout(view.ListLayout):
  def __init__(self, parent, events, track):
    self._events = events
    self._track = track
    view.ListLayout.__init__(self, parent, events.controllers, 
                             lambda(n): ControllerView(self._events, n))
    self._track.add_observer(self.layout)
    self._events.add_observer(self.on_events_change)
  def destroy(self):
    self._track.remove_observer(self.layout)
    self._events.remove_observer(self.on_events_change)
    view.ListLayout.destroy(self)
  def on_events_change(self):
    self.items = tuple(self._events.controllers)
  # get the list of items from the controller numbers in the event list
  @property
  def items(self):
    return(self._items)
  @items.setter
  def items(self, value):
    if (value != self._items):
      self._items = value
      self.update_views()
  def layout(self):
    r = self.rect()
    width = r.width()
    height = r.height()
    controller_map = dict()
    i = 0.0
    for number in self._track.controllers:
      controller_map[number] = i
      i += 1.0
    scale_view = self.parentItemWithAttribute('view_scale')
    if (scale_view is not None):
      scale = scale_view.view_scale
      controller_height = scale.controller_height / scale.pitch_height
    else:
      try:
        controller_height = height / float(len(self._track.controllers))
      except ZeroDivisionError:
        controller_height = 1.0
    if (self._views is not None):
      for view in self._views:
        number = view.number
        try:
          y = r.y() + (controller_map[number] * controller_height)
        except KeyError:
          continue
        view.setRect(QRectF(0.0, y, width, controller_height))

# display control changes for a particular controller number
class ControllerView(view.ModelView):
  def __init__(self, events, number, parent=None):
    self._number = number
    view.ModelView.__init__(self, events, parent)
  @property
  def events(self):
    return(self._model)
  @property
  def number(self):
    return(self._number)
  def _paint(self, qp):
    r = self.rect()
    t = qp.deviceTransform()
    px = 1.0 / t.m11()
    py = 1.0 / t.m22()
    qp.setPen(Qt.NoPen)
    qp.setBrush(self.brush())
    last_time = None
    last_value = None
    for event in self.events.ccsets_for_controller(self.number):
      try:
        time = event.time
        number = event.number
        value = event.value
      except AttributeError: continue
      if (number != self._number): continue
      if (last_time is None):
        last_time = time
      elif (time - last_time >= px):
        self.draw_segment(qp, r, last_time, time, last_value, py)
        last_time = time
      last_value = value
    if ((last_time is not None) and (last_time < self.events.duration)):
      self.draw_segment(qp, r, last_time, self._model.duration, value, py)
  # draw a section of constant controller value, 
  #  repeating for the duration of the block
  def draw_segment(self, qp, r, start_time, end_time, value, py):
    y = (2 * py) + ((1.0 - value) * (r.height() - (4 * py)))
    x = start_time
    w = end_time - start_time
    repeat_time = self._model.duration
    while (x < r.width()):
      qp.drawRect(QRectF(x, y - py, w, 2 * py))
      if (repeat_time <= 0): break
      x += repeat_time

# do layout for notes in a block
class NoteLayout(view.ListLayout):
  def __init__(self, parent, notes, track):
    self._track = track
    view.ListLayout.__init__(self, parent, notes, lambda n: NoteView(n))
    self._track.add_observer(self.layout)
  def destroy(self):
    self._track.remove_observer(self.layout)
    view.ListLayout.destroy(self)
  def layout(self):
    pitch_map = dict()
    i = 0.5
    for pitch in reversed(self._track.pitches):
      pitch_map[pitch] = i
      i += 1.0
    if (self._views is not None):
      for view in self._views:
        note = view.note
        try:
          y = pitch_map[note.pitch]
        except KeyError:
          y = -1.0
        view.setPos(QPointF(note.time, y))

# represent a note event in a block
class NoteView(view.TimeDraggable, view.PitchDraggable, view.Deleteable, view.ModelView):
  # the minimum distance from the centerline to the note's edge
  MIN_RADIUS = 0.125
  def __init__(self, note, parent=None):
    self._rect = QRectF()
    self._bounding_rect = QRectF()
    self._shape = None
    view.ModelView.__init__(self, note, parent)
    view.TimeDraggable.__init__(self)
    view.PitchDraggable.__init__(self)
    view.Deleteable.__init__(self)
    self.note.add_observer(self._update_geometry)
    self._update_geometry()
  def destroy(self):
    self.note.remove_observer(self._update_geometry)
    view.ModelView.destroy(self)
  @property
  def note(self):
    return(self._model)
  # update the note's position
  def setPos(self, pos):
    self._update_geometry()
    view.ModelView.setPos(self, pos)
  # update the note's geometry
  def _update_geometry(self):
    self.prepareGeometryChange()
    # invalidate the cached shape
    self._shape = None
    # give the note a minimum size, so it's selectable even if small
    t = self.sceneTransform()
    sx = t.m11()
    sy = t.m22()
    min_duration = 0.5 * (sy / sx)
    # update the rectangle and bounding rectangle
    note = self.note
    pitch = note.pitch
    ymin = (note.pitch - note.max_pitch) - 0.5
    ymax = (note.pitch - note.min_pitch) + 0.5
    r = QRectF(0.0, ymin, max(min_duration, note.duration), ymax - ymin)
    self._bounding_rect = r
    pos = self.pos()
    self._rect = QRectF(r.x() + pos.x(), r.y() + pos.y(), r.width(), r.height())
    self.update()
  # get the note's extents
  def rect(self):
    return(self._rect)
  def boundingRect(self):
    return(self._bounding_rect)
  # allow the note to have a complex interaction area
  def shape(self):
    if (self._shape is None):
      note = self.note
      self._shape = QPainterPath()
      # make a box around very short notes or notes without bends
      min_duration = self._bounding_rect.width()
      if ((note.duration < min_duration) or (len(note.bend) < 2)):
        self._shape.addRect(QRectF(0.0, - 0.5, 
          max(min_duration, note.duration), 1.0))
      else:
        uppers = list()
        lowers = list()
        for (time, bend) in note.bend:
          uppers.append(QPointF(time, bend - 0.5))
          lowers.append(QPointF(time, bend + 0.5))
        lowers.reverse()
        self._shape.addPolygon(uppers + lowers)
    return(self._shape)
  def _paint(self, qp):
    selected = self.note.selected
    role = QPalette.Highlight if selected else QPalette.WindowText
    color = self.palette.color(QPalette.Normal, role)
    qp.setBrush(QBrush(color))
    qp.setPen(Qt.NoPen)
    note = self.note
    # get the transform to pixels
    t = qp.deviceTransform()
    sx = t.m11()
    sy = t.m22()
    # get the note's initial velocity
    velocity = 1.0
    try:
      velocity = note.velocity
    except AttributeError: pass
    # make a function to convert velocity to a radius from the centerline
    def vr(velocity):
      return(self.MIN_RADIUS + ((0.5 - self.MIN_RADIUS) * velocity))
    # if the note is very short, like a percussion hit, we can draw a triangle
    #  to represent it
    if ((note.duration * sx) < (0.5 * sy)):
      r = vr(velocity)
      w = (r * sy) / sx
      qp.drawPolygon((QPointF(0.0, -r), QPointF(0.0, r), QPointF(w, 0.0)))
      return
    # if the note has no bends or aftertouch, we can optimize by drawing a rectangle
    elif ((len(note.bend) < 2) and (len(note.aftertouch) < 2)):
      r = vr(velocity)
      qp.drawRect(QRectF(0.0, -r, note.duration, 2 * r))
      return
    # make a routine to return the slope between two points for interpolation
    def slope(a, b):
      try:
        return((b[1] - a[1]) / (b[0] - a[0]))
      except ZeroDivisionError:
        return(0.0)
    # draw bends and aftertouch changes
    bends = note.bend
    if (len(bends) < 2):
      bends = ((0.0, 0.0), (note.duration, 0.0))
    velocities = note.aftertouch
    if (len(velocities) < 2):
      velocities = ((0.0, velocity), (note.duration, velocity))
    bend = bends[0]
    bindex = 1
    next_bend = bends[bindex]
    bslope = slope(bend, next_bend)
    velocity = velocities[0]
    vindex = 1
    next_velocity = velocities[vindex]
    vslope = slope(velocity, next_velocity)
    uppers = list()
    lowers = list()
    t = 0.0
    while (t <= note.duration):
      y = bend[1]
      r = vr(velocity[1])
      uppers.append(QPointF(t, y - r))
      lowers.append(QPointF(t, y + r))
      if ((next_velocity[0] > t) and
          (next_velocity[0] < next_bend[0]) and 
          (vindex < len(velocities))):
        dt = next_velocity[0] - t
        t = next_velocity[0]
        velocity = next_velocity
        vindex += 1
        if (vindex < len(velocities)):
          next_velocity = velocities[vindex]
          vslope = slope(velocity, next_velocity)
        else:
          vslope = 0.0
        bend = (t, bend[1] + (dt * bslope))
      elif ((next_bend[0] > t) and
            (next_bend[0] <= next_velocity[0]) and 
            (bindex < len(bends))):
        dt = next_bend[0] - t
        t = next_bend[0]
        bend = next_bend
        bindex += 1
        if (bindex < len(bends)):
          next_bend = bends[bindex]
          bslope = slope(bend, next_bend)
        else:
          bslope = 0.0
        velocity = (t, velocity[1] + (dt * vslope))
      elif (t < note.duration):
        t = note.duration
      else:
        break
    lowers.reverse()
    qp.drawPolygon(uppers + lowers)
    
# represent the start of a block
class BlockStartView(view.TimeDraggable, view.ModelView):
  WIDTH = 6.0
  def __init__(self, model, parent=None):
    view.ModelView.__init__(self, model, parent)
    view.TimeDraggable.__init__(self)
    self.setCursor(Qt.SizeHorCursor)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, self.WIDTH, 0.0))
    return(QRectF(0.0, 0.0, r.width(), self.rect().height()))
  def _paint(self, qp):
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
class BlockEndView(view.TimeDraggable, view.ModelView):
  WIDTH = 6.0
  def __init__(self, model, parent=None):
    view.ModelView.__init__(self, model, parent)
    view.TimeDraggable.__init__(self)
    self.setCursor(Qt.SizeHorCursor)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, self.WIDTH, 0.0))
    return(QRectF(- r.width(), 0.0, r.width(), self.rect().height()))
  def _paint(self, qp):
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
class BlockRepeatView(view.TimeDraggable, view.ModelView):
  WIDTH = 12.0
  def __init__(self, model, parent=None):
    view.ModelView.__init__(self, model, parent)
    view.TimeDraggable.__init__(self)
    self.setCursor(Qt.SizeHorCursor)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, 1.0, 0.0))
    px = r.width()
    return(QRectF(- ((self.WIDTH - 1) * px), 0.0, 
      self.WIDTH * px, self.rect().height()))
  def _paint(self, qp):
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

