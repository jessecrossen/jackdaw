import math
import cairo

from PySide.QtCore import *
from PySide.QtGui import *

#import symbols
import core
from ..models.doc import ViewScale
from ..models import doc
import block

# an overlay for a track list that shows the state of the transport
class TransportView(core.ModelView):
  def __init__(self, transport, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=transport, parent=parent)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.update)
  @property
  def transport(self):
    return(self._model)
  def paint(self, qp, options, widget):
    r = self.rect()
    width = r.width()
    height = r.height()
    pps = self.view_scale.pixels_per_second
    x = round((self.transport.time - self.view_scale.time_offset) * pps)
    if (x >= 0):
      qp.setBrush(self.brush(0.10))
      qp.setPen(Qt.NoPen)
      qp.drawRect(0, 0, x, height)
      pen = QPen(QColor(255, 0, 0, 128))
      pen.setWidth(2)
      qp.setPen(pen)
      qp.drawLine(QPointF(x, 0.0), QPointF(x, height))
    
# make a view that displays a list of tracks
class TrackListView(core.BoxSelectable, core.Interactive, core.ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=tracks, parent=parent)
    core.Interactive.__init__(self)
    core.BoxSelectable.__init__(self)
    self.scrollbar = None
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.transport = transport
    self.track_layout = core.VBoxLayout(self, tracks,
      lambda t: TrackView(t, view_scale=view_scale))
    # add a view for the transport
    self.overlay = TransportView(
      transport=self.transport,
      view_scale=self.view_scale,
      parent=self)
    # enable clipping of children, so tracks can scroll/zoom
    # without going outside the box
    self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
  @property
  def tracks(self):
    return(self._model)
  def paint(self, qp, options, widget):
    width = self._size.width()
    height = self._size.height()
    qp.setPen(Qt.NoPen)
    qp.setBrush(QBrush(QColor(255, 0, 0, 32)))
    qp.drawRect(0, 0, width, height)
    r = QRectF(0, 0, width, height)
    self.track_layout.setRect(r)
    self.overlay.setRect(r)
    # add a scrollbar to scroll through the timeline
    if ((not self.scrollbar) and (self.scene())):
      self.scrollbar = QScrollBar(Qt.Orientation.Horizontal)
      proxy = self.scene().addWidget(self.scrollbar)
      proxy.setParent(self)
      self.scrollbar.valueChanged.connect(self.on_scroll)
    if (self.scrollbar):
      # position the scrollbar
      g = self.scrollbar.geometry()
      self.scrollbar.setGeometry(0, height - g.height(), width, g.height())
      # update its range to fit the timeline, using milliseconds because
      #  it can't have a float value
      shown_duration = width / self.view_scale.pixels_per_second
      max_duration = 0
      for track in self.tracks:
        max_duration = max(max_duration, track.duration)
      shown_duration = min(shown_duration, max_duration)
      maximum = max_duration - shown_duration
      self.scrollbar.setMaximum(int(math.ceil(maximum * 1000)))
      self.scrollbar.setPageStep(int(math.floor(shown_duration * 1000)))
      self.scrollbar.setSingleStep(1000)
  # handle scrolling
  def on_scroll(self):
    time = float(self.scrollbar.value()) / 1000.0
    self.view_scale.time_offset = time
  # clear the selection when clicked
  def on_click(self, event):
    if (event.modifiers() == 0):
      doc.Selection.deselect_all()
  @property
  def track(self):
    return(self._model)

# do layout of blocks in a track
class TrackLayout(core.ListLayout):
  @property
  def track(self):
    return(self._items)
  def layout(self):
    y = self._rect.y()
    r = self.mapRectFromParent(self._rect)
    h = r.height()
    for view in self._views:
      x = view.model.time
      try:
        w = view.model.duration
      except AttributeError:
        w = view.rect().width()
      view.setRect(QRectF(x, y, w, h))

# show a track
class TrackView(core.ModelView):
  def __init__(self, track, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_scale)
    # add a layout for the blocks
    self.block_layout = TrackLayout(self, track, 
      lambda b: block.BlockView(b, track=track))
    self.on_scale()
  @property
  def track(self):
    return(self._model)
  # respond to scaling
  def on_scale(self):
    t = QTransform()
    t.scale(self.view_scale.pixels_per_second, self.view_scale.pitch_height)
    t.translate(- self.view_scale.time_offset, 0)
    self.block_layout.setTransform(t)
  # provide a height for layout in the parent
  def rect(self):
    r = core.ModelView.rect(self)
    r.setHeight(len(self.track.pitches) * self.view_scale.pitch_height)
    return(r)
  # update the placement of the layout
  def paint(self, qp, options, widget):
    r = self.rect()
    width = r.width()
    height = r.height()
    self.block_layout.setRect(QRectF(0, 0, width, height))

## show a label for a pitch on the track
#class PitchNameView(QLineEdit):
#  def __init__(self, track, pitch, parent=None):
#    QLineEdit.__init__(self, parent)
#    # link to the track and index
#    self._track = track
#    self._pitch = None
#    self.pitch = pitch
#    # draw with no frame and a transparent background
#    self.setFrame(False)
#    p = self.palette()
#    p.setBrush(QPalette.Base, Qt.NoBrush)
#    self.setPalette(p)
#    self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
#    self.textEdited.connect(self.on_edited)
#    self.editingFinished.connect(self.on_edit_finished)
#  @property
#  def pitch(self):
#    return(self._pitch)
#  @pitch.setter
#  def pitch(self, value):
#    if (value != self._pitch):
#      self._pitch = value
#      self._update_name()
#  def _update_name(self):
#    self.setText(self._track.name_of_pitch(self._pitch))
#  def on_edited(self, text):
#    if (len(text) > 0):
#      self._track.pitch_names[self._pitch] = text
#    else:
#      try:
#        del self._track.pitch_names[self._pitch]
#      except KeyError: pass
#    self._track.on_change()
#    self.updateGeometry()
#  def on_edit_finished(self):
#    self._update_name()
#  def sizeHint(self):
#    return(self.minimumSizeHint())
#  def minimumSizeHint(self):
#    s = QLineEdit.sizeHint(self)
#    fm = QFontMetrics(self.font())
#    s.setWidth(fm.width('  '+self.text()))
#    return(s)

## do layout for the pitches of a track
#class PitchKeyLayout(QVBoxLayout):
#  def __init__(self, track, view_scale, parent=None):
#    QVBoxLayout.__init__(self, parent)
#    self.view_scale = view_scale
#    # attach to the track
#    self._track = track
#    self._track.add_observer(self.on_change)
#    self.setSpacing(0)
#    self.setContentsMargins(0, 0, 0, 0)
#    self.update_views()
#    # add some stretch at the end so the labels have a truly fixed height
#    self.addStretch(1)
#  @property
#  def track(self):
#    return(self._track)
#  def on_change(self):
#    self.update_views()
#  def update_views(self):
#    if (not self._track): return
#    i = 0
#    last = None
#    for pitch in reversed(self._track.pitches):
#      item = self.itemAt(i)
#      if ((item is None) or (item.widget() is None)):
#        name_view = PitchNameView(self._track, pitch)
#        self.insertWidget(i, name_view)
#      else:
#        name_view = item.widget()
#      name_view.pitch = pitch
#      name_view.setFixedHeight(self.view_scale.pitch_height)
#      if ((self.parentWidget() is not None) and (last is not None)):
#        QWidget.setTabOrder(last, name_view)
#      last = name_view
#      i += 1
#    count = self.count()
#    unused = list()
#    if (i < count):
#      for j in range(i, count):
#        widget = self.itemAt(j).widget()
#        if (widget):
#          unused.append(widget)
#    for widget in unused:
#       self.removeWidget(widget)
#       widget.setParent(None)
## show names for the pitches on a track
#class PitchKeyView(core.ModelView):
#  def __init__(self, track, view_scale=None, parent=None):
#    core.ModelView.__init__(self, model=track, parent=parent)
#    if (view_scale is None):
#      view_scale = ViewScale()
#    self.view_scale = view_scale
#    # add a layout for the pitches
#    self.setLayout(PitchKeyLayout(track, view_scale=self.view_scale))

