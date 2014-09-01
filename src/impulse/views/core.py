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
    if (hasattr(self, 'redraw')):
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

# a mixin to add selectability to a model view
class Selectable(object):
  def mousePressEvent(self, event):
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

# make a layout class with basic array management
class ListLayout(QLayout):
  def __init__(self):
    QLayout.__init__(self)
    self._items = list()
  def addItem(self, item):
    self._items.append(item)
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
      self.invalidate()
      return(item)
    else:
      return(None)

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
    if (self.update_views()):
      self.invalidate()
  def update_views(self):
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

