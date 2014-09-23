# coding=utf-8

import math

from PySide.QtCore import *
from PySide.QtGui import *

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
    
# make a base class for input/output ports
class UnitPortView(core.ModelView):
  RADIUS = 4.0
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

# show an input port to a unit
class UnitInputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    w = (r * 4.0) + 1
    h = (r * 2.0) + 2
    return(QRectF(- w, - (h / 2), w, h))
  def paint(self, qp, options, widget):
    self.drawPort(qp, QPointF(0.0, 0.0), 
                  QPointF(- (self.RADIUS * 3.0), 0.0))
# show an output port to a unit
class UnitOutputView(UnitPortView):
  def boundingRect(self):
    r = self.RADIUS
    w = (r * 4.0) + 1
    h = (r * 2.0) + 2
    return(QRectF(0, - (h / 2), w, h))
  def paint(self, qp, options, widget):
    self.drawPort(qp, QPointF(0.0, 0.0), 
                  QPointF(self.RADIUS * 3.0, 0.0))

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
    return(self._rect.left())
# lay out unit inputs for a list of items
class OutputListLayout(PortListLayout):
  def base_x(self):
    return(self._rect.right())

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
