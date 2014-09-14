from PySide.QtCore import *
from PySide.QtGui import *

import core
import track
from ..models import doc
#import device
#from ..midi import inputs, outputs, sampler

class DocumentView(QGraphicsView):
  def __init__(self, document, parent=None):
    self.scene = QGraphicsScene()
    QGraphicsView.__init__(self, self.scene, parent)
    self._document = document
    # enable antialiasing
    self.setRenderHints(QPainter.Antialiasing)
    # draw the background like a plain window background
    self.setBackgroundBrush(QPalette().brush(QPalette.Normal, QPalette.Window))
    # add views
    self.track_list_view = track.TrackListView(
            tracks=document.tracks,
            transport=document.transport, 
            view_scale=self.document.view_scale)
    self.track_list_view.setRect(QRectF(0, 0, 600, 200))
    self.scene.addItem(self.track_list_view)
    
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
    
