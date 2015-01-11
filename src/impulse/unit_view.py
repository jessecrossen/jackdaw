import math

from PySide.QtCore import *
from PySide.QtGui import *

import unit
import view
from undo import UndoManager
from button_view import DeleteButton, AddButton, DragButton, ResizeButton

class UnitView(view.Selectable, view.ModelView):
  # define a mapping from unit classes to specific view classes
  _unit_class_to_view_class = dict()
  # the margin to leave around the content
  MARGIN = 10.0
  # the height of the bar at the top, containing the title and buttons
  TOP_HEIGHT = 24.0
  # the height of the bar at the bottom, containing the add and resize buttons
  BOTTOM_HEIGHT = 24.0
  def __init__(self, *args, **kwargs):
    view.ModelView.__init__(self, *args, **kwargs)
    view.Selectable.__init__(self)
    self.title_proxy = None
    self._size = QSizeF(60.0, 40.0)
    self._content = None
    self._input_layout = None
    self._output_layout = None
    self.allow_delete = False
    self._delete_button = None
    self._drag_button = None
    self.allow_resize_width = False
    self.allow_resize_height = False
    self._resize_button = None
    self.allow_add = False
    self._add_button = None
    # editing the title may change the width of the unit
    self.unit.name_changed.connect(self.on_name_changed)
    # show a normal cursor to override the workspace cursor
    self.setCursor(Qt.ArrowCursor)
  def destroy(self):
    self.unit.name_changed.disconnect(self.on_name_changed)
    # removing the content will change the unit view's geometry briefly
    self.prepareGeometryChange()
    view.ModelView.destroy(self)  
  @property
  def unit(self):
    return(self._model)
  # return whether the unit view is being moved or resized
  @property
  def moving(self):
    return(((self._drag_button) and (self._drag_button.dragging)) or
           ((self._resize_button) and (self._resize_button.dragging)))
  # register a class for use as a unit view
  @classmethod
  def register_unit_view(cls, unit_class, view_class):
    cls._unit_class_to_view_class[unit_class] = view_class
  # get an appropriate view for a unit
  @classmethod
  def view_for_unit(cls, unit):
    unit_class = unit.__class__
    if (unit_class in cls._unit_class_to_view_class):
      view_class = cls._unit_class_to_view_class[unit_class]
      return(view_class(unit))
    return(UnitView(unit))
  # handle the user wanting to remove the unit
  def on_delete(self):
    document_view = self.parentItemWithAttribute('document')
    if (document_view):
      document = document_view.document
      inputs = ()
      outputs = ()
      if (self._input_layout is not None):
        inputs = self._input_layout.items
      if (self._output_layout is not None):
        outputs = self._output_layout.items
      document.remove_unit(self.unit, inputs=inputs, outputs=outputs)
  # handle the user wanting to add to the unit (this will have different 
  #  behaviors depending on the type of unit)
  def on_add(self):
    pass
  # get the size of the content (override for independent sizing)
  def content_size(self):
    return(self._content.boundingRect().size())
  # manage the rect to keep it centered on the content size
  def rect(self):
    r = view.ModelView.rect(self)
    if (self._content):
      m = self.MARGIN
      content_size = self.content_size()
      w = content_size.width() + (m * 2)
      h = content_size.height() + (m * 2)
      h += self.TOP_HEIGHT
      if ((self.allow_resize_width) or (self.allow_resize_height) or 
          (self.allow_add)):
        h += self.BOTTOM_HEIGHT
      r.setWidth(w)
      r.setHeight(h)
    # make sure there's enough space for the title
    top_width = (2 * self.TOP_HEIGHT)
    if (self.title_proxy):
      title_view = self.title_proxy.widget()
      tr = title_view.minimumSizeHint()
      top_width += tr.width()
    r.setWidth(max(r.width(), top_width))
    return(r)
  def setRect(self, rect):
    posChanged = ((rect.x() != self.pos().x()) or
                  (rect.y() != self.pos().y()))
    if (posChanged):
      self.prepareGeometryChange()
      self.setPos(rect.x(), rect.y())
  def on_name_changed(self):
    self.prepareGeometryChange()
    self.layout()
  def layout(self):
    top_height = self.TOP_HEIGHT
    bottom_height = self.BOTTOM_HEIGHT
    # add a title label at the top
    if ((self.scene()) and (not self.title_proxy)):
      title_view = view.NameLabel(self.unit)
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
        self._delete_button = DeleteButton(self)
        self._delete_button.clicked.connect(self.on_delete)
      if (self._delete_button):
        self._delete_button.setRect(
          QRectF(r.right() - top_height, r.top(), top_height, top_height))
    elif (self._delete_button):
      self._delete_button.destroy()
      self._delete_button = None
    # make a button to add to the unit
    if (self.allow_add):
      if ((self.scene()) and (not self._add_button)):
        self._add_button = AddButton(self)
        self._add_button.clicked.connect(self.on_add)
      if (self._add_button):
        self._add_button.setRect(
          QRectF(r.left(), r.bottom() - bottom_height, 
                 bottom_height, bottom_height))
    elif (self._add_button):
      self._add_button.destroy()
      self._add_button = None
    # make a button to drag the unit
    if ((self.scene()) and (not self._drag_button)):
      self._drag_button = DragButton(self, self.unit)
    if (self._drag_button):
      self._drag_button.setRect(
        QRectF(r.left(), r.top(), top_height, top_height))
    # make a button to resize the unit
    if ((self.allow_resize_width) or (self.allow_resize_height)):
      if ((self.scene()) and (not self._resize_button)):
        self._resize_button = ResizeButton(self, 
          target=self.unit,
          horizontal=self.allow_resize_width, 
          vertical=self.allow_resize_height)
      if (self._resize_button):
        self._resize_button.setRect(
          QRectF(r.right() - bottom_height, r.bottom() - bottom_height, 
                 bottom_height, bottom_height))
    elif (self._resize_button):
      self._resize_button.destroy()
      self._resize_button = None
    # position the content, if any
    m = self.MARGIN
    content_pos = QPointF(m, m + top_height)
    content_height = 0.0
    if (self._content):
      self._content.setPos(content_pos)
      content_height = self._content.boundingRect().height()
    # position inputs and outputs left and right of the content
    io_rect = QRectF(0.0, content_pos.y(), 
                     r.width(), content_height)
    if (self._input_layout):
      self._input_layout.setRect(io_rect)
    if (self._output_layout):
      self._output_layout.setRect(io_rect)
  # draw a box enclosing the content and title
  def _paint(self, qp):
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    if (self.unit.selected):
      qp.setBrush(self.brush(0.30))
    elif (self.unit.hue is not None):
      color = QColor()
      color.setHsvF(self.unit.hue, 1.0, 1.0, 0.30)
      qp.setBrush(QBrush(color))
    else:
      qp.setBrush(self.brush(0.15))
    r = self.boundingRect()
    r.adjust(1, 1, -1, -1)
    qp.drawRoundedRect(r, 4.0, 4.0)

class GroupUnitView(UnitView):
  def __init__(self, *args, **kwargs):
    UnitView.__init__(self, *args, **kwargs)
    self.allow_delete = True
    # make a dummy placeholder view for content
    self._content = QGraphicsRectItem(self)
    self._content.setVisible(False)
    self._group_rect = QRectF()
    # put groups behind other units and the connections layer (which has 
    #  a z-value of -1.0)
    self.setZValue(- 2.0)
  # override layout to ensure the group view contains all grouped units
  def setRect(self, r):
    parent = self.parentItem()
    if (parent is None): return
    siblings = parent.childItems()
    gr = QRectF()
    for view in siblings:
      if ((hasattr(view, 'unit')) and (view.unit in self.unit.units)):
        vr = view.rect()
        if ((gr.width() == 0.0) and (gr.height() == 0.0)):
          gr = vr
        else:
          gr = gr.united(vr)
    # add a margin around the content
    cm = int(1.5 * self.MARGIN)
    gr.adjust(- cm, - cm, cm, cm)
    self._group_rect = gr
    # leave room for the unit view's elements and borders
    m = self.MARGIN
    r = QRectF(gr)
    r.adjust(- m, - self.TOP_HEIGHT, m, 0.0)
    UnitView.setRect(self, r)
  def content_size(self):
    return(self._group_rect.size())  
    
UnitView.register_unit_view(unit.GroupUnit, GroupUnitView)

# show a connection between two ports
class ConnectionView(view.Selectable, view.ModelView):
  # the radius of the pluggable ends of the wire
  RADIUS = 3.5
  # the minimum distance to offset the control points so that the 
  #  wire makes smooth curves into its endpoints
  CURVE = 40.0
  def __init__(self, *args, **kwargs):
    view.ModelView.__init__(self, *args, **kwargs)
    view.Selectable.__init__(self)
    self.allow_multiselect = False
    self._source_view = None
    self._sink_view = None
    self._source_pos = QPointF(0, 0)
    self._sink_pos = QPointF(0, 0)
    # show a hand cursor to indicate that connections are draggable
    self.setCursor(Qt.OpenHandCursor)
  def destroy(self):
    self._source_view = None
    self._sink_view = None
    view.ModelView.destroy(self)
  @property
  def connection(self):
    return(self._model)
  @property
  def patch_bay(self):
    workspace_view = self.parentItemWithAttribute('patch_bay')
    if (workspace_view):
      return(workspace_view.patch_bay)
    else:
      return(None)
  @property
  def source_view(self):
    return(self._source_view)
  @source_view.setter
  def source_view(self, value):
    if (value is not self._source_view):
      self._disconnect_port_view(self._source_view)
      self._source_view = value
      self._connect_port_view(self._source_view)
      self.on_moved()
  @property
  def sink_view(self):
    return(self._sink_view)
  @sink_view.setter
  def sink_view(self, value):
    if (value is not self._sink_view):
      self._disconnect_port_view(self._sink_view)
      self._sink_view = value
      self._connect_port_view(self._sink_view)
      self.on_moved()
  @property
  def port_type(self):
    if ((isinstance(self._source_view, UnitPortView)) and 
        (isinstance(self._sink_view, UnitPortView))):
      # if either end of an audio connection is mono, only mono data 
      #  can pass over it
      if ((self._source_view.port_type == 'mono') or 
          (self._sink_view.port_type == 'mono')):
        return('mono')
      else:
        return(self._source_view.port_type)
    if (isinstance(self._source_view, UnitPortView)):
      return(self._source_view.port_type)
    elif (isinstance(self._sink_view, UnitPortView)):
      return(self._sink_view.port_type)
    return(None)
  def _connect_port_view(self, view):
    if (isinstance(view, UnitPortView)):
      view.moved.connect(self.on_moved)
      view.destroyed.connect(self.on_port_destroyed)
  def _disconnect_port_view(self, view):
    if (view is UnitPortView):
      view.moved.disconnect(self.on_moved)
      view.destroyed.disconnect(self.on_port_destroyed)
  # respond to the source or sink view being destroyed
  def on_port_destroyed(self):
    self.destroy()
  # respond to the source or sink being moved
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
    self._sink_pos = get_pos(self._sink_view)
    self.update()
  # get the bounding rectangle encompassing the source and sink
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
    # get the source and sink as points, mapping into local coordinates
    source = self._source_pos
    sink = self._sink_pos
    # compute a curvature that will look good
    dx = sink.x() - source.x()
    dy = sink.y() - source.y()
    min_curve = min(abs(dy), self.CURVE)
    x_curve = max(min_curve, abs(dx / 2.0))
    y_curve = 0.0
    if (dx < 0):
      sign = 1.0 if dy >= 0 else -1.0
      y_curve = (x_curve / 4.0) * sign
    # place endpoints and control points
    return((source, 
            QPointF(source.x() + x_curve, source.y() + y_curve),
            QPointF(sink.x() - x_curve, sink.y() - y_curve),
            sink))
  # get a path for the wire part of the connection
  def wirePath(self):
    path = QPainterPath()
    (source, cp1, cp2, sink) = self.curvePoints()
    path.moveTo(source)
    path.cubicTo(cp1, cp2, sink)
    return(path)
  # define the shape to be an outset from the wire area
  def shape(self):
    stroker = QPainterPathStroker()
    stroker.setWidth(2 * (self.RADIUS + 1))
    stroker.setCapStyle(Qt.RoundCap)
    return(stroker.createStroke(self.wirePath()))
  # draw the connection as a wire
  def _paint(self, qp):
    # make sure there is a parent and endpoints
    if ((self.source_view is None) or (self.sink_view is None) or
        (self.parentItem() is None)): return
    # make a pen and brush
    if (self.connection.hue is not None):
      color = QColor()
      color.setHsvF(self.connection.hue, 1.0, 1.0)
      pen = QPen(color)
      brush = QBrush(color)
    else:
      pen = self.pen()
      brush = self.brush()
    # draw the wire
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(Qt.NoBrush)
    # if the connection is carrying stereo data (i.e. both ends are stereo)
    #  draw it as a doubled line
    if (self.port_type == 'stereo'):
      stroker = QPainterPathStroker()
      stroker.setWidth(4.0)
      stroker.setCapStyle(Qt.FlatCap)
      qp.drawPath(stroker.createStroke(self.wirePath()))
    else:
      qp.drawPath(self.wirePath())
    # draw the endpoints
    qp.setPen(Qt.NoPen)
    qp.setBrush(brush)
    self._draw_endpoint(qp, self._source_pos, self.RADIUS)
    self._draw_endpoint(qp, self._sink_pos, self.RADIUS)
  # draw an endpoint at the given point
  def _draw_endpoint(self, qp, p, r):
    port_type = self.port_type
    # draw a square to indicate midi
    if (port_type == 'midi'):
      qp.drawPolygon((
        QPointF(p.x() - r, p.y()), QPointF(p.x(), p.y() - r),
        QPointF(p.x() + r, p.y()), QPointF(p.x(), p.y() + r)))
    # draw a circle otherwise
    else:
      qp.drawEllipse(p, r, r)
  # allow the ends of the connection to be dragged out of their ports
  def on_drag_start(self, event):
    UndoManager.begin_action((self.connection, self.patch_bay))
    pos = event.pos()
    source = self._source_pos
    sink = self._sink_pos
    source_dist = abs(pos.x() - source.x()) + abs(pos.y() - source.y())
    sink_dist = abs(pos.x() - sink.x()) + abs(pos.y() - sink.y())
    self._drag_sink = (sink_dist < source_dist)
    QApplication.instance().setOverrideCursor(Qt.ClosedHandCursor)
  def on_drag(self, event, delta_x, delta_y):
    p = event.scenePos()
    item = self.scene().itemAt(p)
    if (self._drag_sink):
      if ((isinstance(item, UnitInputView)) and 
          (item.port_type == self.source_view.port_type) and
          (item.port is not self.source_view.port)):
        self.sink_view = item
      else:
        self.sink_view = p
    else:
      if ((isinstance(item, UnitOutputView)) and 
          (item.port_type == self.sink_view.port_type) and
          (item.port is not self.sink_view.port)):
        self.source_view = item
      else:
        self.source_view = p
  def on_drag_end(self, event):
    self.finalize_connection()
    QApplication.instance().restoreOverrideCursor()
    UndoManager.end_action()
  # remove the connection when it's selected and the user presses delete
  def keyPressEvent(self, event):
    if ((self.connection.selected) and 
        (event.key() == Qt.Key_Delete) or (event.key() == Qt.Key_Backspace)):
      self.on_delete()
    else:
      event.ignore()
  def on_delete(self):
    self.connection.source = None
    self.connection.sink = None
    self.destroy()
  # deselect the connection if it loses focus
  def focusOutEvent(self, event):
    self.connection.selected = False
  # finalize the view's connection or remove it
  def finalize_connection(self):
    if ((isinstance(self.source_view, UnitOutputView)) and 
        (isinstance(self.sink_view, UnitInputView))):
      self.connection.source = self.source_view.target
      self.connection.sink = self.sink_view.target
      patch_bay = self.patch_bay
      if (patch_bay is not None):
        patch_bay.append(self.connection)
    else:
      self.connection.source = None
      self.connection.sink = None
      self.destroy()

# make a base class for input/output ports
class UnitPortView(view.Interactive, view.ModelView):
  # a signal to be sent if the item changes its position
  moved = Signal()
  # the radius of the open ring at the end of the port
  RADIUS = 4.0
  # the distance from the base of the port to the center of its ring
  OFFSET = RADIUS * 3.0
  def __init__(self, *args, **kwargs):
    view.ModelView.__init__(self, *args, **kwargs)
    view.Interactive.__init__(self)
    self._dragging_connection_view = None
    self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
    self.setCursor(Qt.OpenHandCursor)
  @property
  def target(self):
    return(self._model)
  @property
  def patch_bay(self):
    workspace_view = self.parentItemWithAttribute('patch_bay')
    if (workspace_view is not None):
      return(workspace_view.patch_bay)
    return(None)
  # get the type of signal the port accepts
  @property
  def port_type(self):
    return(None)
  # signal when position changes
  def itemChange(self, change, value):
    if (change == QGraphicsItem.ItemScenePositionHasChanged):
      self.moved.emit()
    return(view.ModelView.itemChange(self, change, value))
  # do generalized painting for a port
  def drawPort(self, qp, base, end):
    qp.setBrush(Qt.NoBrush)
    pen = self.pen()
    pen.setWidth(2.0)
    pen.setCapStyle(Qt.FlatCap)
    pen.setJoinStyle(Qt.MiterJoin)
    qp.setPen(pen)
    r = self.RADIUS
    # draw midi connections with square ends
    port_type = self.port_type
    if (port_type == 'midi'):
      qp.drawPolygon((
        QPointF(end.x() - r, end.y()),
        QPointF(end.x(), end.y() - r),
        QPointF(end.x() + r, end.y()),
        QPointF(end.x(), end.y() + r)
      ))
    # draw audio connections with round ends
    else:
      qp.drawEllipse(end, r, r)
    dx = base.x() - end.x()
    dy = base.y() - end.y()
    d = math.sqrt(math.pow(dx, 2) + math.pow(dy, 2))
    f = r / d
    p = QPointF(end.x() + (f * dx), end.y() + (f * dy))
    # draw a double line if the port is stereo
    if (port_type == 'stereo'):
      dx = (dx / d) * 2
      dy = (dy / d) * 2
      qp.drawLine(QPointF(p.x() + dy, p.y() - dx), QPointF(base.x() + dy, base.y() - dx))
      qp.drawLine(QPointF(p.x() - dy, p.y() + dx), QPointF(base.x() - dy, base.y() + dx))
    # otherwise draw a single line
    else:
      qp.drawLine(p, base)
  # handle dragging a connection from a port
  def on_drag_start(self, event):
    UndoManager.begin_action(self.patch_bay)
    # make a connection and add it to the workspace
    connection = unit.Connection()
    view = ConnectionView(connection)
    if (isinstance(self, UnitOutputView)):
      view.source_view = self
    else:
      view.sink_view = self
    workspace_view = self.parentItemWithAttribute('connection_layer')
    if (workspace_view):
      view.setParentItem(workspace_view.connection_layer)
    else:
      view.setParentItem(self)
    self._dragging_connection_view = view
    QApplication.instance().setOverrideCursor(Qt.ClosedHandCursor)
  def on_drag(self, event, delta_x, delta_y):
    view = self._dragging_connection_view
    if (not view): return
    p = event.scenePos()
    item = self.scene().itemAt(p)
    if (view.source_view is self):
      if ((isinstance(item, UnitInputView)) and 
          (item.port_type == self.port_type) and 
          (item.port is not self.port)):
        view.sink_view = item
      else:
        view.sink_view = p
    else:
      if ((isinstance(item, UnitOutputView)) and 
          (item.port_type == self.port_type) and 
          (item.port is not self.port)):
        view.source_view = item
      else:
        view.source_view = p
  def on_drag_end(self, event):
    view = self._dragging_connection_view
    self._dragging_connection_view = None
    # remove the view if it didn't form a connection
    view.finalize_connection()
    QApplication.instance().restoreOverrideCursor()
    UndoManager.end_action()
  # when added to the scene, automatically add views for any 
  #  connections to or from the target
  def on_added_to_scene(self):
    view.ModelView.on_added_to_scene(self)
    workspace_view = self.parentItemWithAttribute('patch_bay')
    if (workspace_view is not None):
      workspace_view.autoconnect()

# show an input port to a unit
class UnitInputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    x = - (r * 2.0)
    h = (r * 4.0)
    return(QRectF(x, - (h / 2), self.OFFSET - x, h))
  def _paint(self, qp):
    self.drawPort(qp, QPointF(self.OFFSET, 0.0), 
                      QPointF(0.0, 0.0))
  @property
  def port(self):
    try:
      return(self.target.sink_port)
    except AttributeError:
      return(None)
  @property
  def port_type(self):
    try:
      return(self.target.sink_type)
    except AttributeError:
      return(None)
# show an output port to a unit
class UnitOutputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    w = self.OFFSET + (r * 2.0)
    h = (r * 4.0)
    return(QRectF(- self.OFFSET, - (h / 2), w, h))
  def _paint(self, qp):
    self.drawPort(qp, QPointF(- self.OFFSET, 0.0), 
                      QPointF(0.0, 0.0))
  @property
  def port(self):
    try:
      return(self.target.source_port)
    except AttributeError:
      return(None)
  @property
  def port_type(self):
    try:
      return(self.target.source_type)
    except AttributeError:
      return(None)

# lay out input/output ports for a unit
class PortListLayout(view.ListLayout):
  def __init__(self, *args, **kwargs):
    def y_of_view(rect, view, i, view_count):
      y = rect.y()
      h = rect.height() / view_count
      return(y + ((float(i) + 0.5) * h))
    self.y_of_view = y_of_view
    view.ListLayout.__init__(self, *args, **kwargs)
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
