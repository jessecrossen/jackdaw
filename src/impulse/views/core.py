import math
import weakref

from PySide.QtCore import *
from PySide.QtGui import *

from ..common import observable
from ..models import doc
import state

# make a base class for views
class ModelView(QGraphicsObject):
  def __init__(self, model, parent=None):
    QGraphicsObject.__init__(self, parent)
    self._model = model
    self._model.add_observer(self.update)
    self._palette = QPalette()
    self._size = QSizeF(0.0, 0.0)
  @property
  def model(self):
    return(self._model)
  @property
  def palette(self):
    return(self._palette)
  @palette.setter
  def palette(self, value):
    self._palette = value
    self.on_change()
  # make a qt-style getter/setter for the area of the item
  def rect(self):
    pos = self.pos()
    return(QRectF(pos.x(), pos.y(), self._size.width(), self._size.height()))
  def setRect(self, rect):
    if ((rect.x() != self.pos().x()) or
        (rect.y() != self.pos().y()) or
        (rect.width() != self._size.width()) or 
        (rect.height() != self._size.height())):
      self.setPos(rect.x(), rect.y())
      self._size = QSizeF(rect.width(), rect.height())
      self.update()
  # make a default implementation of the bounding box
  def boundingRect(self):
    r = self.rect()
    return(QRectF(0.0, 0.0, r.width(), r.height()))
  # redraw the view
  def paint(self, qp, options, widget):
    pass
  # get a brush based on the model's selection state
  def brush(self, alpha=1.0):
    try:
      selected = self.model.selected
    except AttributeError:
      selected = False
    role = QPalette.Highlight if selected else QPalette.WindowText
    color = self.palette.color(QPalette.Normal, role)
    if (alpha < 1.0):
      color.setAlphaF(alpha)
    return(QBrush(color))
  # get a pen based on the model's selection state
  def pen(self, alpha=1.0):
    selected = self.model.selected
    role = QPalette.Highlight if selected else QPalette.WindowText
    color = self.palette.color(QPalette.Normal, role)
    if (alpha < 1.0):
      color.setAlphaF(alpha)
    return(QPen(color))

# make a view interactive
class Interactive(object):
  def __init__(self):
    self._dragging = False
    self._drag_start_pos = None
    self.setFlag(QGraphicsItem.ItemIsFocusable, True)
  # handle mouse events
  def mousePressEvent(self, event):
    self._dragging = False
    self._drag_start_pos = event.scenePos()
  def mouseMoveEvent(self, event):
    pos = event.scenePos()
    scene_delta = QPointF(
      pos.x() - self._drag_start_pos.x(),
      pos.y() - self._drag_start_pos.y())
    delta = self.mapFromScene(scene_delta)
    delta -= self.mapFromScene(QPointF(0, 0))
    if ((not self._dragging) and 
        ((abs(scene_delta.x()) >= 6) or (abs(scene_delta.y()) >= 6))):
      self._dragging = True
      self.on_drag_start(event)
    if (self._dragging):
      self.on_drag(event, delta.x(), delta.y())
  def mouseReleaseEvent(self, event):
    if (self._dragging):
      self.on_drag_end(event)
      self._dragging = False
    else:
      self.on_click(event)
  # override these to handle mouse events in general
  def on_click(self, event):
    pass
  def on_drag_start(self, event):
    self.on_drag_start_x(event)
    self.on_drag_start_y(event)
  def on_drag(self, event, delta_x, delta_y):
    self.on_drag_x(event, delta_x)
    self.on_drag_y(event, delta_y)
  def on_drag_end(self, event):
    self.on_drag_end_x(event)
    self.on_drag_end_y(event)
  # override these to handle drag axes separately
  def on_drag_start_x(self, event):
    pass
  def on_drag_start_y(self, event):
    pass
  def on_drag_x(self, event, delta_x):
    pass
  def on_drag_y(self, event, delta_y):
    pass
  def on_drag_end_x(self, event):
    pass
  def on_drag_end_y(self, event):
    pass
  # handle keyboard events
  def keyPressEvent(self, event):
    # route arrow keys
    if ((event.key() == Qt.Key_Left) or (event.key() == Qt.Key_Right)):
      self.on_key_x(event);
    elif ((event.key() == Qt.Key_Up) or (event.key() == Qt.Key_Down)):
      self.on_key_y(event)
    else:
      event.ignore()
  # override these to handle arrow key axes separately
  def on_key_x(self, event):
    pass
  def on_key_y(self, event):
    pass

# a mixin to add selectability to an interactive view
class Selectable(Interactive):
  def __init__(self):
    Interactive.__init__(self)
  def on_click(self, event):
    if (event.modifiers() == Qt.ShiftModifier):
      self.model.selected = True
    elif (event.modifiers() == Qt.ControlModifier):
      self.model.selected = not self.model.selected
    else:
      if (self.model.selected):
        event.ignore()
        return
      doc.Selection.deselect_all()
      self.model.selected = True

# make a view allow box selection by dragging
class BoxSelectable(Interactive, ModelView):
  def __init__(self):
    self._box_origin = None
    self._box_rect = None
    self._box_view = None
  def map_rect(self, r, source, dest):
    tl = r.topLeft()
    br = r.bottomRight()
    tl = dest.mapFromGlobal(source.mapToGlobal(tl))
    br = dest.mapFromGlobal(source.mapToGlobal(br))
    r = QRectF(tl.x(), tl.y(), br.x() - tl.x(), br.y() - tl.y())
    return(r.normalized())
  def mousePressEvent(self, event):
    if (not self.model.selected):
      self._box_origin = event.pos()
      self._box_rect = QRectF(
        self._box_origin.x(), self._box_origin.y(), 0.0, 0.0)
      self._box_view = QGraphicsRectItem()
      pen = QPen(QColor(0, 0, 0, 128))
      pen.setWidth(2)
      pen.setDashPattern((2, 3))
      self._box_view.setPen(pen)
      self._box_view.setBrush(Qt.NoBrush)
      self.scene().addItem(self._box_view)
    else:
      Interactive.mousePressEvent(self, event)
  def mouseMoveEvent(self, event):
    if (self._box_rect is not None):
      origin = self._box_origin
      pos = event.pos()
      r = QRectF(origin.x(), origin.y(),
        pos.x() - origin.x(), pos.y() - origin.y()).normalized()
      g = self.boundingRect()
      r = r.intersected(QRect(-5, -5, g.width() + 10, g.height() + 10))
      self._box_rect = r
      self._box_view.setRect(
        self.mapRectToScene(self._box_rect))
    else:
      Interactive.mouseMoveEvent(self, event)
  def mouseReleaseEvent(self, event):
    r = self._box_rect
    self._box_rect = None
    self._box_origin = None
    if (self._box_view):
      self.scene().removeItem(self._box_view)
      self._box_view = None
    if (r):
      min_dim = min(r.width(), r.height())
      if (min_dim >= 6):
        self.select_box(event, r)
        return
    Interactive.mouseReleaseEvent(self, event)
  def select_box(self, event, r):
    modifiers = event.modifiers()
    if ((modifiers != Qt.ShiftModifier) and 
        (modifiers != Qt.ControlModifier)):
      doc.Selection.deselect_all()
    self._select_children_in_box(self, r, modifiers, set())
  def _select_children_in_box(self, item, r, modifiers, visited):
    for child in item.childItems():
      cr = self.mapRectToItem(item, r)
      br = child.mapRectToParent(child.boundingRect())
      if ((isinstance(child, Selectable)) and (cr.contains(br))):
        if (child.model in visited): continue
        visited.add(child.model)
        if (modifiers == Qt.ControlModifier):
          child.model.selected = not child.model.selected
        else:
          child.model.selected = True
        if (child.model.selected):
          child.setFocus()
      else:
        self._select_children_in_box(child, r, modifiers, visited)

# a mixin to allow a view's model time to be dragged horizontally
class TimeDraggable(Selectable):
  def __init__(self):
    Selectable.__init__(self)
    self._drag_start_times = dict()
  # get the interval of time to jump when shift is pressed
  def _get_time_jump(self, delta_time):
    sign = 1.0 if delta_time >= 0 else -1.0
    node = self
    while(node):
      try:
        model = node.model
        if (hasattr(model, 'events')):
          model = model.events
      except AttributeError: pass
      else:
        if ((hasattr(model, 'divisions')) and 
            (hasattr(model, 'duration')) and 
            (model.divisions > 1)):
          return(sign * (float(model.duration) / float(model.divisions)))
      node = node.parentItem()
    return(delta_time * 10.0)
  def on_drag_start_x(self, event):  
    # select the model if it isn't selected
    if (not self.model.selected):
      doc.Selection.deselect_all()
      self.model.selected = True
    # record the original times of all selected models
    self._drag_start_times = dict()
    for model in doc.Selection.models:
      try:
        self._drag_start_times[model] = model.time
      except AttributeError: continue
  def on_drag_x(self, event, delta_time):
    for model in doc.Selection.models:
      if (model in self._drag_start_times):
        model.time = self._drag_start_times[model] + delta_time
  # reset state after dragging to avoid memory leaks
  def on_drag_end_x(self, event):
    self._drag_start_times = dict()
  # handle keypresses
  def on_key_x(self, event):
    # get the time difference equivalent to one pixel
    delta_time = self.mapFromScene(1, 0).x() - self.mapFromScene(0, 0).x()
    if (event.key() == Qt.Key_Left):
      delta_time *= -1
    # make a bigger jump when the shift key is down
    if (event.modifiers() == Qt.ShiftModifier):
      delta_time = self._get_time_jump(delta_time)
    # apply to the selection
    for model in doc.Selection.models:
      model.time += delta_time

# a mixin to allow a view's pitch to be dragged vertically
class PitchDraggable(Selectable):
  def __init__(self):
    Selectable.__init__(self)
    self._drag_start_pitches = dict()
  def on_drag_start_y(self, event):
    # select the model if it isn't selected
    if (not self.model.selected):
      doc.Selection.deselect_all()
      self.model.selected = True
    # record the original pitches of all selected models
    self._drag_start_pitches = dict()
    for model in doc.Selection.models:
      try:
        self._drag_start_pitches[model] = model.pitch
      except AttributeError: continue
  def on_drag_y(self, event, delta_y):
    sign = -1 if delta_y > 0 else 1
    delta_pitch = sign * int(math.floor(abs(delta_y)))
    for model in doc.Selection.models:
      if (model in self._drag_start_pitches):
        model.pitch = self._drag_start_pitches[model] + delta_pitch
  # reset state after dragging to avoid memory leaks
  def on_drag_end_y(self, event):
    self._drag_start_pitches = dict()
  # handle keypresses
  def on_key_y(self, event):
    # get the time difference equivalent to one pixel
    delta_pitch = 1
    if (event.key() == Qt.Key_Down):
      delta_pitch *= -1
    # make a bigger jump when the shift key is down
    if (event.modifiers() == Qt.ShiftModifier):
      delta_pitch *= 12
    # apply to the selection
    for model in doc.Selection.models:
      model.pitch += delta_pitch

# make a class that manages graphics items representing a list
class ListLayout(QGraphicsObject):
  def __init__(self, parent, items, view_for_item):
    QGraphicsObject.__init__(self, parent)
    self.view_for_item = view_for_item
    self._view_map = dict()
    self._views = list()
    self._items = items
    self._rect = QRectF(0, 0, 0, 0)
    try:
      self._items.add_observer(self.update_views)
    except AttributeError: pass
    self.update_views()
  def container(self):
    return(self._container)
  def rect(self):
    return(self._rect)
  def setRect(self, rect):
    self._rect = rect
    self.layout()
  def boundingRect(self):
    return(QRectF())
  def paint(self, qp, options, widget):
    pass
  def update_views(self):
    old = set(self._view_map.keys())
    new = set()
    views = list()
    for item in self._items:
      if (item in self._view_map):
        old.remove(item)
        view = self._view_map[item]
      else:
        view = self.view_for_item(item)
        if (view is None): continue
        new.add(item)
        view.setParentItem(self)
        self._view_map[item] = view
        try:
          item.add_observer(self.layout)
        except AttributeError: pass
      views.append(view)
    for item in old:
      view = self._view_map[item]
      view.setParentItem(None)
      self.scene.removeItem(view)
      del self._view_map[item]
      try:
        item.remove_observer(self.layout)
      except AttributeError: pass
    self._views = views
    if ((len(old) > 0) or (len(new) > 0)):
      self.layout()
  def layout(self):
    pass

class VBoxLayout(ListLayout):
  def layout(self):
    y = self._rect.y()
    x = self._rect.x()
    w = self._rect.width()
    for view in self._views:
      r = view.rect()
      view.setRect(QRectF(x, y, w, r.height()))
      y += r.height()

# make a singleton for handling things like selection state
class ViewManagerSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self.reset()
  # reset the state of the manager
  def reset(self):
    # whether snapping to event times is enabled
    self.snap_time = True
    # the time difference within which to snap, in seconds
    self.snap_window = 0.15
    # the time that has been snapped to
    self._snapped_time = None
    # make a stack to manage undo operations
    self._undo_stack = state.UndoStack()
    self._action_things = None
    self._end_action_timer = QTimer()
    self._end_action_timer.setSingleShot(True)
    self._end_action_timer.timeout.connect(self.end_action)
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
      if (self._end_action_timer.isActive()):
        self._end_action_timer.stop()
      else:
        first_one = True
      self._end_action_timer.start(end_timeout)
    elif (self._end_action_timer is not None):
      self._end_action_timer.stop()
      self.end_action()
    if (first_one):
      self._action_things = (things, doc.Selection)
      self._undo_stack.begin_action(self._action_things)
      self.on_change()
  def end_action(self):
    self._undo_stack.end_action(self._action_things)
    self._action_things = None
    self.on_change()
    self._end_action_timer.stop()
    return(False)
# make a singleton instance
ViewManager = ViewManagerSingleton()

