# coding=utf-8

import math

from PySide.QtCore import *
from PySide.QtGui import *

from ..models import unit

import core
import track

class UnitView(core.ModelView):
  MARGIN = 10.0
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    self.title_proxy = None
    self._size = QSizeF(60.0, 40.0)
    self._content = None
    self._input_layout = None
    self._output_layout = None
  @property
  def unit(self):
    return(self._model)
  def rect(self):
    r = core.ModelView.rect(self)
    if (self._content):
      cr = self._content.boundingRect()
      m = self.MARGIN
      w = cr.width() + (m * 2)
      h = cr.height() + (m * 2)
      if (self.title_proxy):
        h += self.title_proxy.widget().geometry().height()
      r.setWidth(w)
      r.setHeight(h)
    return(r)
  def layout(self):
    # add a title label at the top
    if ((self.scene()) and (not self.title_proxy)):
      title_view = core.NameLabel(self.unit)
      self.title_proxy = self.scene().addWidget(title_view)
      self.title_proxy.setParentItem(self)
    r = self.boundingRect()
    title_height = 0
    if (self.title_proxy):
      title_view = self.title_proxy.widget()
      title_view.setFixedWidth(r.width())
      self.title_proxy.setPos(QPointF(0.0, 0.0))
      title_height = title_view.geometry().height()
    # position the content, if any
    m = self.MARGIN
    content_pos = QPointF(m, m + title_height)
    if (self._content):
      self._content.setPos(content_pos)
    # position inputs and outputs left and right of the content
    io_rect = QRectF(0.0, content_pos.y(), 
                     r.width(), r.height() - content_pos.y())
    if (self._input_layout):
      self._input_layout.setRect(io_rect)
    if (self._output_layout):
      self._output_layout.setRect(io_rect)
  # draw a box enclosing the content and title
  def paint(self, qp, options, widget):
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(self.brush(0.15))
    r = self.boundingRect()
    r.adjust(-1, -1, -1, -1)
    qp.drawRoundedRect(r, 4.0, 4.0)

# show a connection between two ports
class ConnectionView(core.Interactive, core.ModelView):
  # the radius of the pluggable ends of the wire
  RADIUS = 3.5
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    core.Interactive.__init__(self)
    self._source_view = None
    self._dest_view = None
  @property
  def connection(self):
    return(self._model)
  @property
  def source_view(self):
    return(self._source_view)
  @source_view.setter
  def source_view(self, value):
    if (value is not self._source_view):
      self.prepareGeometryChange()
      self._source_view = value
      self.update()
  @property
  def dest_view(self):
    return(self._dest_view)
  @dest_view.setter
  def dest_view(self, value):
    if (value is not self._dest_view):
      self.prepareGeometryChange()
      self._dest_view = value
      self.update()
  # get the local coordinates for source and destination points
  def sourcePos(self):
    if (not self.source_view):
      return(QPointF(0.0, 0.0)) 
    elif (isinstance(self.source_view, QPointF)):
      source = self.source_view
    else:
      source = self.source_view.mapToScene(QPointF(0.0, 0.0))
    return(self.mapFromScene(source))
  def destPos(self):
    if (not self.dest_view):
      return(QPointF(0.0, 0.0)) 
    elif (isinstance(self.dest_view, QPointF)):
      dest = self.dest_view
    else:
      dest = self.dest_view.mapToScene(QPointF(0.0, 0.0))
    return(self.mapFromScene(dest))
  # get the bounding rectangle encompassing the source and destination
  def boundingRect(self):
    p1 = self.sourcePos()
    p2 = self.destPos()
    r = QRectF(p1.x(), p1.y(), p2.x() - p1.x(), p2.y() - p1.y())
    r = r.normalized()
    m = self.RADIUS
    r.adjust(- m, - m, m, m)
    return(r)
  # draw the connection as a wire
  def paint(self, qp, options, widget):
    # make sure there is a parent and endpoints
    if ((self.source_view is None) or (self.dest_view is None) or
        (self.parentItem() is None)): return
    # get the source and dest as points, mapping into local coordinates
    source = self.sourcePos()
    dest = self.destPos()
    # draw the wire
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(source)
    curve = (dest.x() - source.x()) / 2.0
    path.cubicTo(QPointF(source.x() + curve, source.y()),
                 QPointF(dest.x() - curve, dest.y()),
                 dest)
    qp.drawPath(path)
    # draw the endpoints
    qp.setPen(Qt.NoPen)
    qp.setBrush(self.brush())
    r = self.RADIUS
    qp.drawEllipse(source, r, r)
    qp.drawEllipse(dest, r, r)

# make a base class for input/output ports
class UnitPortView(core.Interactive, core.ModelView):
  # the radius of the open ring at the end of the port
  RADIUS = 4.0
  # the distance from the base of the port to the center of its ring
  OFFSET = RADIUS * 3.0
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    core.Interactive.__init__(self)
    self._dragging_connection_view = None
  @property
  def target(self):
    return(self._model)
  # do generalize painting for a port
  def drawPort(self, qp, base, end):
    qp.setBrush(Qt.NoBrush)
    pen = self.pen()
    pen.setWidth(2.0)
    pen.setCapStyle(Qt.FlatCap)
    qp.setPen(pen)
    r = self.RADIUS
    qp.drawEllipse(end, r, r)
    dx = base.x() - end.x()
    dy = base.y() - end.y()
    d = math.sqrt(math.pow(dx, 2) + math.pow(dy, 2))
    f = r / d
    p = QPointF(end.x() + (f * dx), end.y() + (f * dy))
    qp.drawLine(p, base)
  # handle dragging a connection from a port
  def on_drag_start(self, event):
    connection = unit.Connection()
    view = ConnectionView(connection)
    if (isinstance(self, UnitOutputView)):
      connection.source = self.target
      view.source_view = self
    else:
      connection.dest = self.target
      view.dest_view = self
    node = self
    while (node):
      if (isinstance(node, WorkspaceView)):
        view.setParentItem(node)
        break
      node = node.parentItem()
    if (not node):
      view.setParentItem(self)
    self._dragging_connection_view = view
  def on_drag(self, event, delta_x, delta_y):
    view = self._dragging_connection_view
    if (not view): return
    p = event.scenePos()
    if (view.source_view is self):
      view.dest_view = p
    else:
      view.source_view = p
  def on_drag_end(self, event):
    self._dragging_connection_view.setParentItem(None)
    self._dragging_connection_view = None

# show an input port to a unit
class UnitInputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    x = - (r * 2.0)
    h = (r * 4.0)
    return(QRectF(x, - (h / 2), self.OFFSET - x, h))
  def paint(self, qp, options, widget):
    self.drawPort(qp, QPointF(self.OFFSET, 0.0), 
                      QPointF(0.0, 0.0))
# show an output port to a unit
class UnitOutputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    w = self.OFFSET + (r * 2.0)
    h = (r * 4.0)
    return(QRectF(- self.OFFSET, - (h / 2), w, h))
  def paint(self, qp, options, widget):
    self.drawPort(qp, QPointF(- self.OFFSET, 0.0), 
                      QPointF(0.0, 0.0))

# lay out input/output ports for a unit
class PortListLayout(core.ListLayout):
  def __init__(self, *args, **kwargs):
    def y_of_view(rect, view, i, view_count):
      y = rect.y()
      h = rect.height() / view_count
      return(y + ((float(i) + 0.5) * h))
    self.y_of_view = y_of_view
    core.ListLayout.__init__(self, *args, **kwargs)
  def base_x(self):
    return(0.0)
  def layout(self):
    r = self._rect
    x = self.base_x()
    y = self._rect.y()
    view_count = len(self._views)
    i = 0
    for view in self._views:
      view.setPos(QPointF(x, self.y_of_view(r, view, i, view_count)))
      i += 1
# lay out unit inputs for a list of items
class InputListLayout(PortListLayout):
  def base_x(self):
    return(self._rect.left() - UnitPortView.OFFSET)
# lay out unit inputs for a list of items
class OutputListLayout(PortListLayout):
  def base_x(self):
    return(self._rect.right() + UnitPortView.OFFSET)

# show a workspace with a list of units
class WorkspaceView(core.ModelView):
  def __init__(self, doc, parent=None):
    core.ModelView.__init__(self, model=doc.units, parent=parent)
    # add a layout for the units
    self.units_layout = UnitListLayout(self, 
      doc.units, self.view_for_unit)
  # get an appropriate view for a unit
  def view_for_unit(self, unit):
    if (hasattr(unit, 'tracks')):
      return(MultitrackUnitView(unit))
    return(UnitView(unit))
  # update the placement of the layout
  def layout(self):
    r = self.rect()
    width = r.width()
    height = r.height()
    self.units_layout.setRect(QRectF(0, 0, width, height))
# lay units out on the workspace
class UnitListLayout(core.ListLayout):
  def layout(self):
    y = self._rect.y()
    x = self._rect.x()
    for view in self._views:
      unit = view.unit
      r = view.rect()
      view.setRect(QRectF(
        # use integer coordinates for sharp antialiasing
        round(x + unit.x - (r.width() / 2.0)), 
        round(y + unit.y - (r.height() / 2.0)), 
        r.width(), r.height()))
        
# make a unit view containing a list of tracks
class MultitrackUnitView(UnitView):
  def __init__(self, *args, **kwargs):
    UnitView.__init__(self, *args, **kwargs)
    self._content = track.TrackListView(
            tracks=self.unit.tracks,
            transport=self.unit.transport, 
            view_scale=self.unit.view_scale)
    self._content.setRect(QRectF(0, 0, 300, 200))
    self._content.setParentItem(self)
    # add inputs and outputs to the track
    self._input_layout = InputListLayout(self, self.unit.tracks,
      lambda t: UnitInputView(t))
    self._output_layout = OutputListLayout(self, self.unit.tracks,
      lambda t: UnitOutputView(t))
    self._input_layout.y_of_view = self.y_of_track
    self._output_layout.y_of_view = self.y_of_track
  def y_of_track(self, rect, view, index, view_count):
    y = rect.y()
    scale = self._content.view_scale
    spacing = scale.track_spacing()
    i = 0
    for track in self.unit.tracks:
      h = scale.height_of_track(track)
      if (i >= index):
        y += (h / 2.0)
        return(y)
      y += h + spacing
      i += 1
    return(y)
