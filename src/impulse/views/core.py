import math
import weakref

from PySide.QtCore import *
from PySide.QtGui import *

from ..common import observable
from ..models import doc
import state

# make a base class for views
class ModelView(QWidget):
  def __init__(self, model, parent=None):
    QWidget.__init__(self, parent)
    self._model = model
    self._model.add_observer(self.on_change)
    self._palette = QPalette()
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
  # redraw the widget if there's a drawing method defined
  def paintEvent(self, e):
    if ((self.model is not None) and (hasattr(self, 'redraw'))):
      qp = QPainter()
      qp.begin(self)
      qp.setPen(Qt.NoPen)
      qp.setBrush(Qt.NoBrush)
      qp.setRenderHint(QPainter.Antialiasing, True)
      qp.setRenderHint(QPainter.TextAntialiasing, True)
      g = self.geometry()
      self.redraw(qp, g.width(), g.height())
      qp.end()
  # get a brush based on the model's selection state
  def brush(self, alpha=1.0):
    selected = self.model.selected
    role = QPalette.Highlight if selected else QPalette.WindowText
    color = self.palette.color(QPalette.Normal, role)
    if (alpha < 1.0):
      color.setAlphaF(alpha)
    return(QBrush(color))
  # update the view when the model changes
  def on_change(self):
    if (hasattr(self, 'redraw')):
      self.repaint()
  # remove references to the widget when removing it
  def destroy(self):
    self._model.remove_observer(self.on_change)
    self._model = None
    QWidget.destroy(self)

# make a view interactive
class Interactive(object):
  def __init__(self):
    self._dragging = False
    self._drag_start_x = None
    self._drag_start_y = None
    # accept keyboard focus
    self.setFocusPolicy(Qt.ClickFocus)
  # handle mouse events
  def mousePressEvent(self, event):
    self._dragging = False
    self._drag_start_x = event.globalX()
    self._drag_start_y = event.globalY()
  def mouseMoveEvent(self, event):
    delta_x = event.globalX() - self._drag_start_x
    delta_y = event.globalY() - self._drag_start_y
    if ((not self._dragging) and 
        ((abs(delta_x) >= 6) or (abs(delta_y) >= 6))):
      self._dragging = True
      self.on_drag_start(event)
    if (self._dragging):
      self.on_drag(event, delta_x, delta_y)
  def mouseReleaseEvent(self, event):
    if (self._dragging):
      self.on_drag_end(event)
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

# a mixin to allow a view's model time to be dragged horizontally
class TimeDraggable(Selectable):
  def __init__(self):
    Selectable.__init__(self)
    self._drag_start_times = dict()
    self._drag_view_scale = None
  # get a scale to use for converting pixels to time
  def _get_view_scale(self):
    node = self
    while (node):
      if (hasattr(node, 'view_scale')):
        return(node.view_scale)
      node = node.parentWidget()
    return(None)
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
    # get a scale for dragging
    self._drag_view_scale = self._get_view_scale()
  def on_drag_x(self, event, delta_x):
    if (not self._drag_view_scale): return
    delta_time = self._drag_view_scale.time_of_x(delta_x)
    for model in doc.Selection.models:
      if (model in self._drag_start_times):
        model.time = self._drag_start_times[model] + delta_time
  # reset state after dragging to avoid memory leaks
  def on_drag_end_x(self, event):
    self._drag_start_times = dict()
    self._drag_view_scale = None
  # handle keypresses
  def on_key_x(self, event):
    scale = self._get_view_scale()
    if (scale is None): return
    # get the time difference equivalent to one pixel
    delta_time = scale.time_of_x(1.0)
    if (event.key() == Qt.Key_Left):
      delta_time *= -1
    # make a bigger jump when the shift key is down
    if (event.modifiers() == Qt.ShiftModifier):
      delta_time *= 10.0
    # apply to the selection
    for model in doc.Selection.models:
      model.time += delta_time

# a mixin to allow a view's pitch to be dragged vertically
class PitchDraggable(Selectable):
  def __init__(self):
    Selectable.__init__(self)
    self._drag_start_pitches = dict()
    self._drag_view_scale = None
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
    # get a scale to use for converting pixels to pitch
    node = self
    while (node):
      if (hasattr(node, 'view_scale')):
        self._drag_view_scale = node.view_scale
        break
      node = node.parentWidget()
  def on_drag_y(self, event, delta_y):
    if (not self._drag_view_scale): return
    sign = 1 if delta_y > 0 else -1
    delta_pitch = sign * int(
      math.floor(abs(delta_y) / self._drag_view_scale.pitch_height))
    for model in doc.Selection.models:
      if (model in self._drag_start_pitches):
        model.pitch = self._drag_start_pitches[model] + delta_pitch
  # reset state after dragging to avoid memory leaks
  def on_drag_end_y(self, event):
    self._drag_start_pitches = dict()
    self._drag_view_scale = None
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

# make a layout class with basic array management
class ListLayout(QLayout):
  def __init__(self):
    QLayout.__init__(self)
    self._items = list()
  def addItem(self, item):
    self._items.append(item)
    if (isinstance(item, QLayout)):
      self.addChildLayout(item)
    self.invalidate()
  def count(self):
    return(len(self._items))
  def itemAt(self, index):
    if ((index >= 0) and (index < len(self._items))):
      return(self._items[index])
    else:
      return(None)
  def takeAt(self, index):
    if ((index >= 0) and (index < len(self._items))):
      item = self._items.pop(index)
      # remove the parent of child layouts
      if (isinstance(item, QLayout)):
        item.setParent(None)
      self.invalidate()
      return(item)
    else:
      return(None)
  # allow layouts to be added as well as widgets
  def addLayout(self, layout):
    self.addItem(layout)
  # destroy the layout and all widgets in it
  def destroy(self):
    while(self.count()):
      child = self.takeAt(0)
      try:
        widget = child.widget()
        widget.destroy()
      except AttributeError:
        try:
          child.destroy()
        except AttributeError: pass

# make a layout class that overlays layouts or widgets on top of eachother
class OverlayLayout(ListLayout):
  def __init__(self):
    ListLayout.__init__(self)
  def setGeometry(self, rect):
    for item in self._items:
      item.setGeometry(rect)

# make a layout class for lists of models
class ModelListLayout(ListLayout):
  def __init__(self, model_list, view_class=ModelView):
    ListLayout.__init__(self)
    self._view_class = view_class
    self._model_list = model_list
    self._model_list.add_observer(self.on_change)
    self.views = list()
    self._view_map = dict()
  def on_change(self):
    self.update_views()
    self.invalidate()
  def update_views(self):
    if (not self._model_list): return(False)
    old = set(self._view_map.keys())
    new = set()
    views = list()
    for model in self._model_list:
      if (model in self._view_map):
        view = self._view_map[model]
        old.remove(model)
      else:
        view = self.get_view_for_model(model)
        self._view_map[model] = view
        self.addWidget(view)
        new.add(view)
      views.append(view)
    for model in old:
      view = self._view_map[model]
      del self._view_map[model]
      try:
        self.removeWidget(view)
      except AttributeError: pass
      view.destroy()
    self.views = views
    # redo layout if the items have changed
    return((len(old) > 0) or (len(new) > 0))
  # remove references to all views when destroyed so they get garbage collected
  def destroy(self):
    self.views = list()
    self._view_map = dict()
    self._model_list.remove_observer(self.on_change)
    self._model_list = None    
    ListLayout.destroy(self)
  # update layout    
  def setGeometry(self, rect):
    QLayout.setGeometry(self, rect)
    if (len(self.views) != len(self._model_list)):
      self.update_views()
    self.do_layout()
  # override this to do custom view creation
  def get_view_for_model(self, model):
    return(self._view_class(model))
  # override this for custom layout
  def do_layout(self):
    pass
    
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

