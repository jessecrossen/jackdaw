# -*- coding: utf-8 -*-

from PySide.QtCore import *
from PySide.QtGui import *

from workspace_view import WorkspaceView
import unit
import sampler

class DocumentView(QGraphicsView):
  def __init__(self, document, parent=None):
    self.scene = DocumentScene()
    QGraphicsView.__init__(self, self.scene, parent)
    self._document = document
    # enable antialiasing
    self.setRenderHints(QPainter.Antialiasing)
    # draw the background like a plain window background
    self.setBackgroundBrush(QPalette().brush(QPalette.Normal, QPalette.Window))
    # add a view of the document workspace
    self.workspace = WorkspaceView(document)
    self.scene.addItem(self.workspace)
    self.scene.workspace_view = self.workspace
  def destroy(self):
    self.workspace.destroy()
    self.workspace = None
  @property
  def document(self):
    return(self._document)
  # control track list zoom
  ZOOMS = (8, 16, 24, 32, 48, 64, 96, 128)
  def _zoom_index(self):
    pps = self._document.view_scale.pixels_per_second
    closest = None
    closest_dist = None
    for i in range(0, len(self.ZOOMS)):
      zoom = self.ZOOMS[i]
      dist = abs(zoom - pps)
      if ((dist < closest_dist) or (closest_dist is None)):
        closest_dist = dist
        closest = i
    return(closest)
  def _apply_zoom_delta(self, delta):
    index = self._zoom_index()
    if (index is None): return
    pps = self._document.view_scale.pixels_per_second
    new_pps = self.ZOOMS[index]
    if (new_pps == pps):
      new_pps = self.ZOOMS[index + delta]
    self._document.view_scale.pixels_per_second = new_pps
  def zoom_in(self, *args):
    self._apply_zoom_delta(1)
  def zoom_out(self, *args):
    self._apply_zoom_delta(-1)
  @property
  def can_zoom_in(self):
    return(self._document.view_scale.pixels_per_second < self.ZOOMS[-1])
  @property
  def can_zoom_out(self):
    return(self._document.view_scale.pixels_per_second > self.ZOOMS[0])

# override the scene to add some custom event handlers
class DocumentScene(QGraphicsScene):
  def __init__(self, *args, **kwargs):
    QGraphicsScene.__init__(self, *args, **kwargs)
    self.workspace_view = None
    self._show_add_cursor = False
  # route context menu events in a more flexible way than the default
  def contextMenuEvent(self, e):
    items = self.items(e.scenePos())
    for item in items:
      item.contextMenuEvent(e)
      if (e.isAccepted()): return
    # route clicks that land on nothing to the workspace itself
    if (len(items) == 0):
      if (self.workspace_view is not None):
        self.workspace_view.contextMenuEvent(e)