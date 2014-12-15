import math

from PySide.QtCore import *
from PySide.QtGui import *

import observable

import view
import menu
from unit_view import UnitView, UnitInputView, UnitOutputView, ConnectionView

import track
import track_view
import midi
import midi_view
import sampler
import sampler_view
import audio
import audio_view
import transport
import transport_view

# show a workspace with a list of units
class WorkspaceView(view.Interactive, view.ModelView):
  def __init__(self, document, parent=None):
    self._bounding_rect = QRectF()
    view.ModelView.__init__(self, model=document.units, parent=parent)
    view.Interactive.__init__(self)
    # keep a reference to the document
    self.document = document
    # add a sub-item for connections to keep them behind the units
    #  for visual and interaction purposes
    self.connection_layer = QGraphicsRectItem(self)
    # add a layout for the units
    self.units_layout = UnitListLayout(self, 
      document.units, UnitView.view_for_unit)
    self.units_layout.extents_changed.connect(self.on_extents_changed)
    # connect to the patch bay
    self.patch_bay = document.patch_bay
    self.patch_bay.add_observer(self.autoconnect)
    # show a cursor that indicates clicking will add a unit
    self.setCursor(Qt.CrossCursor)
  def destroy(self):
    self.units_layout.extents_changed.disconnect(self.on_extents_changed)
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
  # update the extents when the workspace extents change size
  def on_extents_changed(self):
    extents = self.units_layout.extents
    if (self.scene()):
      for view in self.scene().views():
        view.setSceneRect(extents)
    # make the workspace background much larger than the viewport to 
    #   receive all background mouse events
    self.prepareGeometryChange()
    m = 2048
    self._bounding_rect = extents.adjusted(- m, - m, m, m)
  def boundingRect(self):
    return(self._bounding_rect)
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
  # show a context menu with document actions
  def on_click(self, event):
    item = self.scene().itemAt(event.scenePos())
    if (item is not self): return
    add_menu = menu.WorkspaceMenu(document=self.document,
                                  event=event,
                                  parent=event.widget())
    add_menu.popup(event.screenPos())
  
# lay units out on the workspace
class UnitListLayout(view.ListLayout):
  extents_changed = Signal()
  def __init__(self, *args, **kwargs):
    self._extents = QRectF()
    view.ListLayout.__init__(self, *args, **kwargs)
  @property
  def extents(self):
    return(self._extents)
  @extents.setter
  def extents(self, value):
    if (value != self._extents):
      self._extents = value
      self.extents_changed.emit()
  def layout(self):
    y = self._rect.y()
    x = self._rect.x()
    extents = QRectF()
    moving_unit = False
    for view in self._views:
      unit = view.unit
      r = view.rect()
      view_rect = QRectF(
        # use integer coordinates for sharp antialiasing
        round(x + unit.x - (r.width() / 2.0)), 
        round(y + unit.y - (r.height() / 2.0)), 
        r.width(), r.height())
      view.setRect(view_rect)
      extents = extents.united(view_rect)
      try:
        moving_unit = moving_unit or view.moving
      except AttributeError: pass
    # size the workspace to the units in it plus a margin
    m = 100.0
    extents.adjust(- m, - m, m, m)
    old_extents = self.extents
    if (moving_unit):
      extents = extents.united(old_extents)
    self.extents = extents
  