import math

from PySide.QtCore import *
from PySide.QtGui import *

import view
from undo import UndoManager

# implement a simple flat button with an icon
class ButtonView(view.Interactive, view.View):
  # a signal that gets fired when the button is clicked
  clicked = Signal()
  # the amount to inset the icon from the edge of the button
  def __init__(self, *args, **kwargs):
    view.View.__init__(self, *args, **kwargs)
    view.Interactive.__init__(self)
    self.setAcceptHoverEvents(True)
    self._hovering = False
  # convert clicks to a signal
  def on_click(self, event):
    self.clicked.emit()
  # keep track of hover state
  def hoverEnterEvent(self, event):
    self._hovering = True
    self.update()
  def hoverLeaveEvent(self, event):
    self._hovering = False
    self.update()
  # do layout for repainting
  def inset(self):
    return(6.0)
  def _paint(self, qp):
    # center the icon in the button area
    r = self.boundingRect()
    s = max(0, min(r.width(), r.height()) - (self.inset() * 2))
    r = QRectF(r.center().x() - (s / 2.0), r.center().y() - (s / 2.0), s, s)
    qp.setPen(Qt.NoPen)
    color = self.palette.color(QPalette.Normal, QPalette.WindowText)
    color.setAlphaF(0.75 if self._hovering else 0.5)
    qp.setBrush(QBrush(color))
    self.drawIcon(qp, r)
  # override this to draw an icon for the button
  def drawIcon(self, qp, r):
    pass
    
# show a button for deleting and closing things
class DeleteButton(ButtonView):
  def drawIcon(self, qp, r):
    p1 = QPainterPath()
    p1.moveTo(r.topLeft())
    p1.lineTo(r.bottomRight())
    p2 = QPainterPath()
    p2.moveTo(r.topRight())
    p2.lineTo(r.bottomLeft())
    stroker = QPainterPathStroker()
    stroker.setWidth(3.0)
    stroker.setCapStyle(Qt.FlatCap)
    p1 = stroker.createStroke(p1)
    p2 = stroker.createStroke(p2)
    qp.drawPath(p1.united(p2))

# show a button for adding things
class AddButton(ButtonView):
  def drawIcon(self, qp, r):
    x = r.x() + (r.width() / 2.0)
    y = r.y() + (r.height() / 2.0)
    p1 = QPainterPath()
    p1.moveTo(QPointF(x, r.top()))
    p1.lineTo(QPointF(x, r.bottom()))
    p2 = QPainterPath()
    p2.moveTo(QPointF(r.left(), y))
    p2.lineTo(QPointF(r.right(), y))
    stroker = QPainterPathStroker()
    stroker.setWidth(3.0)
    stroker.setCapStyle(Qt.FlatCap)
    p1 = stroker.createStroke(p1)
    p2 = stroker.createStroke(p2)
    qp.drawPath(p1.united(p2))

# show a button for resizing things
class ResizeButton(ButtonView):
  def __init__(self, parent, target=None, horizontal=True, vertical=True):
    ButtonView.__init__(self, parent)
    if (target is None):
      target = parent
    self._target = target
    self._horizontal = horizontal
    self._vertical = vertical
    if ((self._horizontal) and (self._vertical)):
      self.setCursor(Qt.SizeFDiagCursor)
    elif (self._horizontal):
      self.setCursor(Qt.SizeHorCursor)
    elif (self._vertical):
      self.setCursor(Qt.SizeVerCursor)
    self._start_rect = None
    self._start_bounds = None
  def drawIcon(self, qp, r):
    x = r.right()
    y = r.bottom()
    w = 2.0
    for offset in range(1, 12, 4):
      qp.drawPolygon([
        QPointF(x, y - offset),
        QPointF(x, y - (offset + w)),
        QPointF(x - (offset + w), y),
        QPointF(x - offset, y)
      ])
  # handle dragging
  def on_drag_start(self, event):
    UndoManager.begin_action(self._target)
    self._start_rect = self._target.rect()
    self._start_bounds = self._target.boundingRect().normalized()
    if (self._start_bounds.width() == 0):
      self._start_bounds.setWidth(1.0)
    if (self._start_bounds.height() == 0):
      self._start_bounds.setHeight(1.0)
  def on_drag(self, event, delta_x, delta_y):
    if (self._start_rect is not None):
      x = self._start_rect.x()
      y = self._start_rect.y()
      w = max(1.0, self._start_rect.width())
      h = max(1.0, self._start_rect.height())
      br = self._start_bounds
      if (self._horizontal):
        try:
          sx = max(0, (br.right() + delta_x) / br.right())
        except ZeroDivisionError:
          sx = 1.0
        x = ((x - br.left()) + (br.left() * sx))
        w *= sx
      if (self._vertical):
        try:
          sy = max(0, (br.bottom() + delta_y) / br.bottom())
        except ZeroDivisionError:
          sy = 1.0
        y = ((y - br.top()) + (br.top() * sy))
        h *= sy
      try:
        self._target.prepareGeometryChange()
      except AttributeError: pass
      set_rect = False
      if (hasattr(self._target, 'width')):
        self._target.width = w
      elif (self._horizontal):
        set_rect = True
      if (hasattr(self._target, 'height')):
        self._target.height = h
      elif (self._vertical):
        set_rect = True
      if (set_rect):
        self._target.setRect(QRectF(x, y, w, h))
  def on_drag_end(self, event):
    self._start_rect = None
    self._start_bounds = None
    try:
      self._target.on_change()
    except AttributeError: pass
    UndoManager.end_action()

# show a button for dragging things
class DragButton(ButtonView):
  # the diameter of the pips to draw that indicate draggability
  DIAMETER = 3.0
  # the spacing between the pips
  SPACING = 3.0
  def __init__(self, parent, target=None):
    ButtonView.__init__(self, parent)
    if (target is None):
      target = parent
    self._target = target
    self.setCursor(Qt.OpenHandCursor)
    self._start_pos = None
  def inset(self):
    return(3.0)
  def drawIcon(self, qp, r):
    d = self.DIAMETER
    s = self.SPACING
    nx = int(math.floor((r.width() + s) / (d + s)))
    ny = int(math.floor((r.height() + s) / (d + s)))
    w = (nx * d) + ((nx - 1) * s)
    h = (ny * d) + ((ny - 1) * s)
    x = r.center().x() - (w / 2.0)
    y = r.center().y() - (h / 2.0)
    for i in range(0, nx):
      for j in range(0, ny):
        qp.drawEllipse(QRectF(x + (i * (d + s)), y + (j * (d + s)), d, d))
  # change the cursor when the mouse is down
  def mousePressEvent(self, event):
    QApplication.instance().setOverrideCursor(Qt.ClosedHandCursor)
    view.Interactive.mousePressEvent(self, event)
  def mouseReleaseEvent(self, event):
    QApplication.instance().restoreOverrideCursor()
    view.Interactive.mouseReleaseEvent(self, event)
  # handle dragging
  def on_drag_start(self, event):
    UndoManager.begin_action(self._target)
    self._start_pos = self._target.pos()
  def on_drag(self, event, delta_x, delta_y):
    if (self._start_pos is not None):
      self._target.setPos(self._start_pos + QPointF(delta_x, delta_y))
  def on_drag_end(self, event):
    self._start_pos = None
    try:
      self._target.on_change()
    except AttributeError: pass
    UndoManager.end_action()
