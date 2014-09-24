import math

from PySide.QtCore import *
from PySide.QtGui import *

import core

# implement a simple flat button with an icon
class ButtonView(core.Interactive, core.View):
  # a signal that gets fired when the button is clicked
  clicked = Signal()
  # the amount to inset the icon from the edge of the button
  def __init__(self, *args, **kwargs):
    core.View.__init__(self, *args, **kwargs)
    core.Interactive.__init__(self)
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
  def paint(self, qp, options, widget):
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
    self.setCursor(Qt.ClosedHandCursor)
    core.Interactive.mousePressEvent(self, event)
  def mouseReleaseEvent(self, event):
    self.setCursor(Qt.OpenHandCursor)
    core.Interactive.mouseReleaseEvent(self, event)
  # handle dragging
  def on_drag_start(self, event):
    self._start_pos = self._target.pos()
  def on_drag(self, event, delta_x, delta_y):
    if (self._start_pos is not None):
      self._target.setPos(self._start_pos + QPointF(delta_x, delta_y))
  def on_drag_end(self, event):
    self._start_pos = None
