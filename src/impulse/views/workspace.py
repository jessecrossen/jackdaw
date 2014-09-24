# coding=utf-8

import math

from PySide.QtCore import *
from PySide.QtGui import *

from ..models import unit

import core
import track
import button

class UnitView(core.ModelView):
  # the margin to leave around the content
  MARGIN = 10.0
  # the height of the bar at the top, containing the title and buttons
  TOP_HEIGHT = 24.0
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    self.title_proxy = None
    self._size = QSizeF(60.0, 40.0)
    self._content = None
    self._input_layout = None
    self._output_layout = None
    self.allow_delete = True
    self._delete_button = None
    self._drag_button = None
  @property
  def unit(self):
    return(self._model)
  # handle the user wanting to remove the unit
  def on_delete(self):
    # TODO
    pass
  # manage the rect to keep it centered on the content size
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
    top_height = self.TOP_HEIGHT
    # add a title label at the top
    if ((self.scene()) and (not self.title_proxy)):
      title_view = core.NameLabel(self.unit)
      self.title_proxy = self.scene().addWidget(title_view)
      self.title_proxy.setParentItem(self)
    r = self.boundingRect()
    r.adjust(1, 1, -1, -1)
    if (self.title_proxy):
      title_view = self.title_proxy.widget()
      title_view.setFixedWidth(r.width() - (2 * top_height))
      title_height = title_view.geometry().height()
      self.title_proxy.setPos(
        QPointF(top_height, (top_height - title_height) / 2.0))
    # make a button to delete the unit
    if (self.allow_delete):
      if ((self.scene()) and (not self._delete_button)):
        self._delete_button = button.DeleteButton(self)
        self._delete_button.clicked.connect(self.on_delete)
      if (self._delete_button):
        self._delete_button.setRect(
          QRectF(r.right() - top_height, r.top(), top_height, top_height))
    elif (self._delete_button):
      self._delete_button.setParentItem(None)
      self._delete_button = None 
    # make a button to drag the unit
    if ((self.scene()) and (not self._drag_button)):
      b = button.DragButton(self, self.unit)
      self._drag_button = b
    if (self._drag_button):
      self._drag_button.setRect(
        QRectF(r.left(), r.top(), top_height, top_height))
    # position the content, if any
    m = self.MARGIN
    content_pos = QPointF(m, m + top_height)
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
    r.adjust(1, 1, -1, -1)
    qp.drawRoundedRect(r, 4.0, 4.0)

# show a connection between two ports
class ConnectionView(core.Selectable, core.ModelView):
  # the radius of the pluggable ends of the wire
  RADIUS = 3.5
  # the minimum distance to offset the control points so that the 
  #  wire makes smooth curves into its endpoints
  CURVE = 40.0
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    core.Selectable.__init__(self)
    self.allow_multiselect = False
    self._source_view = None
    self._dest_view = None
    self._source_pos = QPointF(0, 0)
    self._dest_pos = QPointF(0, 0)
  @property
  def connection(self):
    return(self._model)
  @property
  def source_view(self):
    return(self._source_view)
  @source_view.setter
  def source_view(self, value):
    if (value is not self._source_view):
      if (self._source_view is UnitPortView):
        self._source_view.moved.disconnect(self.on_moved)
      self._source_view = value
      if (isinstance(self._source_view, UnitPortView)):
        self._source_view.moved.connect(self.on_moved)
      self.on_moved()
  @property
  def dest_view(self):
    return(self._dest_view)
  @dest_view.setter
  def dest_view(self, value):
    if (value is not self._dest_view):
      if (self._dest_view is UnitPortView):
        self._dest_view.moved.disconnect(self.on_moved)
      self._dest_view = value
      if (isinstance(self._dest_view, UnitPortView)):
        self._dest_view.moved.connect(self.on_moved)
      self.on_moved()
  # respond to the source or destination being moved
  def on_moved(self):
    self.prepareGeometryChange()
    def get_pos(view):
      if (not view):
        return(QPointF(0.0, 0.0))
      elif (isinstance(view, QPointF)):
        return(self.mapFromScene(QPointF(view.x(), view.y())))
      else:
        return(self.mapFromScene(view.mapToScene(QPointF(0.0, 0.0))))
    self._source_pos = get_pos(self._source_view)
    self._dest_pos = get_pos(self._dest_view)
    self.update()
  # get the bounding rectangle encompassing the source and destination
  def boundingRect(self):
    points = self.curvePoints()
    x_min = 0; x_max = 0
    y_min = 0; y_max = 0
    for p in points:
      x_min = min(x_min, p.x()); x_max = max(x_max, p.x())
      y_min = min(y_min, p.y()); y_max = max(y_max, p.y())
    r = QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
    m = self.RADIUS + 1
    r.adjust(- m, - m, m, m)
    return(r)
  # get the points needed to draw the wire part of the connection
  def curvePoints(self):
    # get the source and dest as points, mapping into local coordinates
    source = self._source_pos
    dest = self._dest_pos
    # compute a curvature that will look good
    dx = dest.x() - source.x()
    dy = dest.y() - source.y()
    min_curve = min(abs(dy), self.CURVE)
    x_curve = max(min_curve, abs(dx / 2.0))
    y_curve = 0.0
    if (dx < 0):
      sign = 1.0 if dy >= 0 else -1.0
      y_curve = (x_curve / 4.0) * sign
    # place endpoints and control points
    return((source, 
            QPointF(source.x() + x_curve, source.y() + y_curve),
            QPointF(dest.x() - x_curve, dest.y() - y_curve),
            dest))
  # get a path for the wire part of the connection
  def wirePath(self):
    path = QPainterPath()
    (source, cp1, cp2, dest) = self.curvePoints()
    path.moveTo(source)
    path.cubicTo(cp1, cp2, dest)
    return(path)
  # define the shape to be an outset from the wire area
  def shape(self):
    stroker = QPainterPathStroker()
    stroker.setWidth(2 * (self.RADIUS + 1))
    stroker.setCapStyle(Qt.RoundCap)
    return(stroker.createStroke(self.wirePath()))
  # draw the connection as a wire
  def paint(self, qp, options, widget):
    # make sure there is a parent and endpoints
    if ((self.source_view is None) or (self.dest_view is None) or
        (self.parentItem() is None)): return
    # draw the wire
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(Qt.NoBrush)
    qp.drawPath(self.wirePath())
    # draw the endpoints
    qp.setPen(Qt.NoPen)
    qp.setBrush(self.brush())
    r = self.RADIUS
    qp.drawEllipse(self._source_pos, r, r)
    qp.drawEllipse(self._dest_pos, r, r)
  # allow the ends of the connection to be dragged out of their ports
  def on_drag_start(self, event):
    pos = event.pos()
    source = self._source_pos
    dest = self._dest_pos
    source_dist = abs(pos.x() - source.x()) + abs(pos.y() - source.y())
    dest_dist = abs(pos.x() - dest.x()) + abs(pos.y() - dest.y())
    self._drag_dest = (dest_dist < source_dist)
  def on_drag(self, event, delta_x, delta_y):
    p = event.scenePos()
    item = self.scene().itemAt(p)
    if (self._drag_dest):
      if (isinstance(item, UnitInputView)):
        self.dest_view = item
      else:
        self.dest_view = p
    else:
      if (isinstance(item, UnitOutputView)):
        self.source_view = item
      else:
        self.source_view = p
  def on_drag_end(self, event):
    self.finalize_connection()
  # remove the connection when it's selected and the user presses delete
  def keyPressEvent(self, event):
    if ((self.connection.selected) and 
        (event.key() == Qt.Key_Delete) or (event.key() == Qt.Key_Backspace)):
      self.connection.source = None
      self.connection.dest = None
      self.setParent(None)
    else:
      event.ignore()
  # deselect the connection if it loses focus
  def focusOutEvent(self, event):
    self.connection.selected = False
  # finalize the view's connection or remove it
  def finalize_connection(self):
    if ((isinstance(self.source_view, UnitOutputView)) and 
        (isinstance(self.dest_view, UnitInputView))):
      self.connection.source = self.source_view.target
      self.connection.dest = self.dest_view.target
    else:
      self.connection.source = None
      self.connection.dest = None
      self.setParent(None)

# make a base class for input/output ports
class UnitPortView(core.Interactive, core.ModelView):
  # a signal to be sent if the item changes its position
  moved = Signal()
  # the radius of the open ring at the end of the port
  RADIUS = 4.0
  # the distance from the base of the port to the center of its ring
  OFFSET = RADIUS * 3.0
  def __init__(self, *args, **kwargs):
    core.ModelView.__init__(self, *args, **kwargs)
    core.Interactive.__init__(self)
    self._dragging_connection_view = None
    self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
  @property
  def target(self):
    return(self._model)
  # signal when position changes
  def itemChange(self, change, value):
    if (change == QGraphicsItem.ItemScenePositionHasChanged):
      self.moved.emit()
    return(core.ModelView.itemChange(self, change, value))
  # do generalized painting for a port
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
      view.source_view = self
    else:
      view.dest_view = self
    node = self
    while (node):
      if (isinstance(node, WorkspaceView)):
        view.setParentItem(node.connection_layer)
        break
      node = node.parentItem()
    if (not node):
      view.setParentItem(self)
    self._dragging_connection_view = view
  def on_drag(self, event, delta_x, delta_y):
    view = self._dragging_connection_view
    if (not view): return
    p = event.scenePos()
    item = self.scene().itemAt(p)
    if (view.source_view is self):
      if (isinstance(item, UnitInputView)):
        view.dest_view = item
      else:
        view.dest_view = p
    else:
      if (isinstance(item, UnitOutputView)):
        view.source_view = item
      else:
        view.source_view = p
  def on_drag_end(self, event):
    view = self._dragging_connection_view
    self._dragging_connection_view = None
    # remove the view if it didn't form a connection
    view.finalize_connection()

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
    # add a sub-item for connections to keep them behind the units
    #  for visual and interaction purposes
    self.connection_layer = QGraphicsRectItem(self)
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
