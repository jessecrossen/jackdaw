# coding=utf-8

import math

from PySide.QtCore import *
from PySide.QtGui import *

import unit

import view
from track_view import TrackListView
from button_view import DeleteButton, AddButton, DragButton, ResizeButton
from midi_view import DeviceListView
from sampler_view import InstrumentListView

class UnitView(view.ModelView):
  # the margin to leave around the content
  MARGIN = 10.0
  # the height of the bar at the top, containing the title and buttons
  TOP_HEIGHT = 24.0
  # the height of the bar at the bottom, containing the add and resize buttons
  BOTTOM_HEIGHT = 24.0
  def __init__(self, *args, **kwargs):
    view.ModelView.__init__(self, *args, **kwargs)
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
  @property
  def unit(self):
    return(self._model)
  # handle the user wanting to remove the unit
  def on_delete(self):
    workspace_view = self.parentItemWithClass(WorkspaceView)
    if (workspace_view):
      workspace_view.units.remove(self.unit)
  # handle the user wanting to add to the unit (this will have different 
  #  behaviors depending on the type of unit)
  def on_add(self):
    pass
  # manage the rect to keep it centered on the content size
  def rect(self):
    r = view.ModelView.rect(self)
    if (self._content):
      cr = self._content.boundingRect()
      m = self.MARGIN
      w = cr.width() + (m * 2)
      h = cr.height() + (m * 2)
      h += self.TOP_HEIGHT
      if ((self.allow_resize_width) or (self.allow_resize_height) or 
          (self.allow_add)):
        h += self.BOTTOM_HEIGHT
      r.setWidth(w)
      r.setHeight(h)
    return(r)
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
  def paint(self, qp, options, widget):
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(self.brush(0.15))
    r = self.boundingRect()
    r.adjust(1, 1, -1, -1)
    qp.drawRoundedRect(r, 4.0, 4.0)

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
  def destroy(self):
    self._source_view = None
    self._sink_view = None
    view.ModelView.destroy(self)
  @property
  def connection(self):
    return(self._model)
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
  def paint(self, qp, options, widget):
    # make sure there is a parent and endpoints
    if ((self.source_view is None) or (self.sink_view is None) or
        (self.parentItem() is None)): return
    # draw the wire
    pen = self.pen()
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
    qp.setBrush(self.brush())
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
    pos = event.pos()
    source = self._source_pos
    sink = self._sink_pos
    source_dist = abs(pos.x() - source.x()) + abs(pos.y() - source.y())
    sink_dist = abs(pos.x() - sink.x()) + abs(pos.y() - sink.y())
    self._drag_sink = (sink_dist < source_dist)
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
  # remove the connection when it's selected and the user presses delete
  def keyPressEvent(self, event):
    if ((self.connection.selected) and 
        (event.key() == Qt.Key_Delete) or (event.key() == Qt.Key_Backspace)):
      self.connection.source = None
      self.connection.sink = None
      self.setParent(None)
    else:
      event.ignore()
  # deselect the connection if it loses focus
  def focusOutEvent(self, event):
    self.connection.selected = False
  # finalize the view's connection or remove it
  def finalize_connection(self):
    if ((isinstance(self.source_view, UnitOutputView)) and 
        (isinstance(self.sink_view, UnitInputView))):
      self.connection.source = self.source_view.target
      self.connection.sink = self.sink_view.target
      workspace_view = self.parentItemWithClass(WorkspaceView)
      if (workspace_view):
        workspace_view.patch_bay.append(self.connection)
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
  @property
  def target(self):
    return(self._model)
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
    # make a connection and add it to the workspace
    connection = unit.Connection()
    view = ConnectionView(connection)
    if (isinstance(self, UnitOutputView)):
      view.source_view = self
    else:
      view.sink_view = self
    workspace_view = self.parentItemWithClass(WorkspaceView)
    if (workspace_view):
      view.setParentItem(workspace_view.connection_layer)
    else:
      view.setParentItem(self)
    self._dragging_connection_view = view
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
  # when added to the scene, automatically add views for any 
  #  connections to or from the target if there are any
  def on_added_to_scene(self):
    view.ModelView.on_added_to_scene(self)
    workspace_view = self.parentItemWithClass(WorkspaceView)
    if (workspace_view):
      patch_bay = workspace_view.patch_bay
      if (((isinstance(self, UnitInputView)) and 
           (len(patch_bay.sources_for_sink(self.target)) > 0)) or
          ((isinstance(self, UnitOutputView)) and 
           (len(patch_bay.sinks_for_source(self.target)) > 0))):
        workspace_view.autoconnect()

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
  def paint(self, qp, options, widget):
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

# show a workspace with a list of units
class WorkspaceView(view.ModelView):
  def __init__(self, doc, parent=None):
    view.ModelView.__init__(self, model=doc.units, parent=parent)
    # add a sub-item for connections to keep them behind the units
    #  for visual and interaction purposes
    self.connection_layer = QGraphicsRectItem(self)
    # add a layout for the units
    self.units_layout = UnitListLayout(self, 
      doc.units, self.view_for_unit)
    # connect to the patch bay
    self.patch_bay = doc.patch_bay
    self.patch_bay.add_observer(self.autoconnect)
  def destroy(self):
    self.patch_bay.remove_observer(self.autoconnect)
    for item in self.connection_layer.childItems():
      try:
        item.destroy()
      except AttributeError:
        item.setParentItem(None)
    view.ModelView.destroy(self)
  @property
  def units(self):
    return(self._model)
  # get an appropriate view for a unit
  def view_for_unit(self, unit):
    if (hasattr(unit, 'tracks')):
      return(MultitrackUnitView(unit))
    elif (hasattr(unit, 'devices')):
      return(DeviceListUnitView(unit))
    elif (hasattr(unit, 'instruments')):
      return(InstrumentListUnitView(unit))
    return(UnitView(unit))
  # update the placement of the layout
  def layout(self):
    r = self.rect()
    width = r.width()
    height = r.height()
    self.units_layout.setRect(QRectF(0, 0, width, height))
  # automatically add connections for an existing port view
  def autoconnect(self):
    # index all connection views by source and sink
    connection_map = dict()
    connection_views = self.connection_layer.childItems()
    for view in connection_views:
      try:
        source = view.source_view.target
      except AttributeError:
        source = None
      try:
        sink = view.sink_view.target
      except AttributeError:
        sink = None
      if ((source is not None) and (sink is not None)):
        connection_map[(source, sink)] = view
    # create maps of input and output views only if needed
    input_map = None
    output_map = None
    # find unconnected connections
    for conn in self.patch_bay:
      # if either end of the connection is missing, it's not valid
      if ((conn.source is None) or (conn.sink is None)): continue
      # skip connections we already have views for
      if ((conn.source, conn.sink) in connection_map): continue
      # index all port views by target
      if ((input_map is None) or (output_map is None)):
        input_map = dict()
        output_map = dict()
        self._index_port_views(self, input_map, output_map)
      # see if we have views for the source and sink
      if ((conn.source in output_map) and (conn.sink in input_map)):
        source_view = output_map[conn.source]
        sink_view = input_map[conn.sink]
        view = ConnectionView(conn, parent=self.connection_layer)
        view.source_view = source_view
        view.sink_view = sink_view
        # add it to the map so we don't do this twice when given a 
        #  double connection
        connection_map[(conn.source, conn.sink)] = view    
  # index all source and destination views
  def _index_port_views(self, node, input_map, output_map):
    children = node.childItems()
    for child in children:
      if (isinstance(child, UnitInputView)):
        input_map[child._model] = child
      elif (isinstance(child, UnitOutputView)):
        output_map[child._model] = child
      else:
        self._index_port_views(child, input_map, output_map)
    
# lay units out on the workspace
class UnitListLayout(view.ListLayout):
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
    self._content = TrackListView(
            tracks=self.unit.tracks,
            transport=self.unit.transport, 
            view_scale=self.unit.view_scale)
    self._content.setParentItem(self)
    # add inputs and outputs to the track
    self._input_layout = InputListLayout(self, self.unit.tracks,
      lambda t: UnitInputView(t))
    self._output_layout = OutputListLayout(self, self.unit.tracks,
      lambda t: UnitOutputView(t))
    self._input_layout.y_of_view = self.y_of_track
    self._output_layout.y_of_view = self.y_of_track
    # allow horizontal resizing
    self.allow_resize_width = True
    # allow tracks to be added
    self.allow_add = True
  def on_add(self):
    self.unit.tracks.add_track()
  def layout(self):
    size = self._content.minimumSizeHint()
    self.unit.width = max(size.width(), self.unit.width)
    self._content.setRect(QRectF(0, 0, self.unit.width, size.height()))
    UnitView.layout(self)
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
    
# make a unit view containing a list of input devices
class DeviceListUnitView(UnitView):
  def __init__(self, *args, **kwargs):
    UnitView.__init__(self, *args, **kwargs)
    self._content = DeviceListView(
      devices=self.unit.devices, 
      require_input=self.unit.require_input,
      require_output=self.unit.require_output)
    self._content.setParentItem(self)
    # add inputs and outputs for the devices
    self._input_layout = InputListLayout(self, self.unit.devices, 
                                            self.input_view_for_device)
    self._output_layout = OutputListLayout(self, self.unit.devices, 
                                            self.output_view_for_device)
  def input_view_for_device(self, device):
    if (not device.has_input):
      if (self.unit.require_input):
        return(None)
      # if the unit has no input, return a placeholder
      return(view.ModelView(device))
    if ((self.unit.require_output) and (not device.has_output)):
      return(None)
    return(UnitInputView(device))
  def output_view_for_device(self, device):
    if (not device.has_output):
      if (self.unit.require_output):
        return(None)
      # if the unit has no output, return a placeholder
      return(view.ModelView(device))
    if ((self.unit.require_input) and (not device.has_input)):
      return(None)
    return(UnitOutputView(device))
  def layout(self):
    size = self._content.minimumSizeHint()
    self._content.setRect(QRectF(0, 0, size.width(), size.height()))
    UnitView.layout(self)

# make a unit view containing a list of sampler instruments
class InstrumentListUnitView(UnitView):
  def __init__(self, *args, **kwargs):
    UnitView.__init__(self, *args, **kwargs)
    self._content = InstrumentListView(
      instruments=self.unit.instruments)
    self._content.setParentItem(self)
    # add inputs and outputs for the instruments
    self._input_layout = InputListLayout(self, self.unit.instruments, 
                                         lambda t: UnitInputView(t))
    self._output_layout = OutputListLayout(self, self.unit.instruments, 
                                           lambda t: UnitOutputView(t))
  def layout(self):
    size = self._content.minimumSizeHint()
    self._content.setRect(QRectF(0, 0, size.width(), size.height()))
    UnitView.layout(self)