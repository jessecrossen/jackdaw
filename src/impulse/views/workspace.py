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
    if (self._content):
      self._content.setPos(QPointF(m, m + title_height))
      
  def paint(self, qp, options, widget):
    pen = self.pen()
    pen.setWidth(2.0)
    qp.setPen(pen)
    qp.setBrush(self.brush(0.15))
    r = self.boundingRect()
    r.adjust(-1, -1, -1, -1)
    qp.drawRoundedRect(r, 4.0, 4.0)
    
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
