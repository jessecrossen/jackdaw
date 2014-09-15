import math
import cairo

from PySide.QtCore import *
from PySide.QtGui import *

#import symbols
import core
from ..models.doc import ViewScale
from ..models import doc
import block

# make a view that displays a list of tracks
class TrackListView(core.BoxSelectable, core.Interactive, core.ModelView):
  SPACING = 6.0
  def __init__(self, tracks, transport, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=tracks, parent=parent)
    core.Interactive.__init__(self)
    core.BoxSelectable.__init__(self)
    self.scrollbar = None
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.view_scale.add_observer(self.update_scrollbar)
    self.transport = transport
    self.pitch_key_layout = core.VBoxLayout(self, tracks,
      lambda t: PitchKeyView(t, view_scale=view_scale))
    self.track_layout = core.VBoxLayout(self, tracks,
      lambda t: TrackView(t, view_scale=view_scale))
    self.pitch_key_layout.spacing = self.SPACING
    self.track_layout.spacing = self.SPACING
    # clip so tracks can be scrolled and zoomed without going outside the box
    self.track_layout.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
    # add a view for the transport
    self.overlay = TransportView(
      transport=self.transport,
      view_scale=self.view_scale,
      parent=self)
  @property
  def tracks(self):
    return(self._model)
  def layout(self):
    width = self._size.width()
    height = self._size.height()
    w = 30
    for view in self.pitch_key_layout.views:
      w = max(w, view.minimumSizeHint().width())
    self.pitch_key_layout.setRect(QRectF(0, 0, w, height))
    x = w + (self.SPACING / 2)
    r = QRectF(x, 0, width - x, height)
    self.track_layout.setRect(r)
    self.overlay.setRect(r)
    # add a scrollbar to scroll through the timeline
    if ((not self.scrollbar) and (self.scene())):
      self.scrollbar = QScrollBar(Qt.Orientation.Horizontal)
      self.scrollbar.valueChanged.connect(self.on_scroll)
      self.scrollbar_proxy = self.scene().addWidget(self.scrollbar)
      self.scrollbar_proxy.setParentItem(self)
    if (self.scrollbar):
      # position the scrollbar
      g = self.scrollbar.geometry()
      self.scrollbar.setGeometry(0, height - g.height(), width, g.height())
    self.update_scrollbar()
  def update_scrollbar(self):
    if (not self.scrollbar): return
    width = self._size.width()
    # update the range to fit the timeline, using milliseconds because
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
      pen.setCapStyle(Qt.FlatCap)
      pen.setWidth(2)
      qp.setPen(pen)
      qp.drawLine(QPointF(x, 0.0), QPointF(x, height))

# do layout of blocks in a track
class TrackLayout(core.ListLayout):
  def __init__(self, *args, **kwargs):
    core.ListLayout.__init__(self, *args, **kwargs)
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
    r.setHeight(self.view_scale.height_of_track(self.track))
    return(r)
  # update the placement of the layout
  def paint(self, qp, options, widget):
    r = self.rect()
    width = r.width()
    height = r.height()
    self.block_layout.setRect(QRectF(0, 0, width, height))

# make a transparent line edit
class TransparentLineEdit(QLineEdit):
  def __init__(self, parent):
    QLineEdit.__init__(self, parent)
    self.setFrame(False)
    p = self.palette()
    p.setBrush(QPalette.Base, Qt.NoBrush)
    self.setPalette(p)
    self.setAutoFillBackground(False)
    self.setStyleSheet("background-color:transparent")
    self.clickedToFocus = False
  # select all on focus
  def mousePressEvent(self, e, Parent=None):
    QLineEdit.mousePressEvent(self, e)
    if (not self.clickedToFocus):
      self.selectAll()
      self.clickedToFocus = True
  def focusOutEvent(self, e):
    QLineEdit.focusOutEvent(self, e)
    self.clickedToFocus = False

# show an editable label for a track's name
class TrackNameView(TransparentLineEdit):
  def __init__(self, track, parent=None):
    TransparentLineEdit.__init__(self, parent)
    # link to the track
    self._track = track
    self._track.add_observer(self._update_name)
    self._update_name()
    self.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
    self.textEdited.connect(self.on_edited)
  def _update_name(self):
    if (not self.hasFocus()):
      self.setText(self._track.name)
  def on_edited(self, text):
    self._track.name = text
  def minimumSizeHint(self):
    s = QLineEdit.sizeHint(self)
    fm = QFontMetrics(self.font())
    s.setWidth(fm.width('  '+self.text()))
    return(s)

# show an editable label for a pitch on the track
class PitchNameView(TransparentLineEdit):
  def __init__(self, track, pitch, parent=None):
    TransparentLineEdit.__init__(self, parent)
    # link to the track and index
    self._track = track
    self._pitch = None
    self.pitch = pitch
    self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    self.textEdited.connect(self.on_edited)
    self.editingFinished.connect(self.on_edit_finished)
  @property
  def pitch(self):
    return(self._pitch)
  @pitch.setter
  def pitch(self, value):
    if (value != self._pitch):
      self._pitch = value
      self._update_name()
  def _update_name(self):
    self.setText(self._track.name_of_pitch(self._pitch))
  def on_edited(self, text):
    if (len(text) > 0):
      self._track.pitch_names[self._pitch] = text
    else:
      try:
        del self._track.pitch_names[self._pitch]
      except KeyError: pass
    self._track.on_change()
  def on_edit_finished(self):
    self._update_name()
  def minimumSizeHint(self):
    s = QLineEdit.sizeHint(self)
    fm = QFontMetrics(self.font())
    s.setWidth(fm.width('  '+self.text()))
    return(s)

# show names for the pitches on a track
class PitchKeyView(core.ModelView):
  SPACING = 6.0
  def __init__(self, track, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.pitch_view_proxies = list()
    self.track_name_proxy = None
  @property
  def track(self):
    return(self._model)
  # provide a height for layout in the parent
  def rect(self):
    r = core.ModelView.rect(self)
    r.setHeight(self.view_scale.height_of_track(self.track))
    return(r)
  def layout(self):
    if (not self.scene()): return
    height = self.rect().height()
    h = self.view_scale.pitch_height
    # make a view for the track name
    if (not self.track_name_proxy):
      self.track_name_proxy = self.scene().addWidget(TrackNameView(self.track))
      self.track_name_proxy.setParentItem(self)
      self.track_name_proxy.setRotation(-90)
    name_view = self.track_name_proxy.widget()
    name_view.setFixedHeight(h)
    name_view.setFixedWidth(height)
    self.track_name_proxy.setPos(QPointF(0.0, height))
    # position the pitch names
    r = self.rect()
    x = h + self.SPACING
    i = 0
    last = None
    for pitch in reversed(self.track.pitches):
      if (i < len(self.pitch_view_proxies)):
        proxy = self.pitch_view_proxies[i]
        proxy.widget().pitch = pitch
      else:
        view = PitchNameView(track=self.track, pitch=pitch)
        view.editingFinished.connect(self.request_resize)
        proxy = self.scene().addWidget(view)
        proxy.setParentItem(self)
        self.pitch_view_proxies.append(proxy)
      proxy.widget().setFixedHeight(self.view_scale.pitch_height)
      proxy.widget().setGeometry(QRect(x, i * h, r.width() - x, h))
      i += 1
    for i in range(len(self.track.pitches), len(self.pitch_view_proxies)):
      proxy = self.pitch_view_proxies.pop()
      self.scene().removeItem(proxy)
      proxy.setParentItem(None)
  # suggest a minimum size that makes room for all the name views
  def minimumSizeHint(self):
    w = 0
    h = 0
    for view in self.pitch_view_proxies:
      s = view.widget().minimumSizeHint()
      w = max(w, s.width())
      h += s.height()
    return(QSize(w + self.SPACING + self.view_scale.pitch_height, h))
  # do layout up the chain so changes to the minimum sizes of the name 
  #  views are propagated through the layout
  def request_resize(self):
    node = self
    while (node):
      node.layout()
      node = node.parentItem()
