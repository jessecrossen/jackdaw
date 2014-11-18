import math

from PySide.QtCore import *
from PySide.QtGui import *

import view
from track_view import TrackListView
from midi_view import DeviceListView
from sampler_view import InstrumentListView

from unit_view import UnitView, ConnectionView

# show a workspace with a list of units
class WorkspaceView(view.ModelView):
  def __init__(self, doc, parent=None):
    view.ModelView.__init__(self, model=doc.units, parent=parent)
    # add a sub-item for connections to keep them behind the units
    #  for visual and interaction purposes
    self.connection_layer = QGraphicsRectItem(self)
    # add a layout for the units
    self.units_layout = UnitListLayout(self, 
      doc.units, UnitView.view_for_unit)
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
