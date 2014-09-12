import math
import cairo

from PySide.QtCore import *
from PySide.QtGui import *

#import symbols
import core
from ..models.doc import ViewScale
from ..models import doc
import block

## do layout of tracks
#class TrackListLayout(QGridLayout):
#  def __init__(self, tracks, transport, parent=None, view_scale=None, margin=1):
#    QGridLayout.__init__(self, parent)
#    if (view_scale is None):
#      view_scale = ViewScale()
#    self.view_scale = view_scale
#    self._margin = margin
#    self.transport = transport
#    # attach to the list of models
#    self._model_list = tracks
#    self._model_list.add_observer(self.on_change)
#    self.update_views()
#    # make a view to go in front of the tracks
#    self.front_view = TrackListFrontView(self.tracks, 
#      transport=self.transport,
#      view_scale=self.view_scale,
#      margin=margin)
#    self.addWidget(self.front_view)
#  @property
#  def tracks(self):
#    return(self._model_list)
#  def on_change(self):
#    self.update_views()
#  def update_views(self):
#    if (not self._model_list): return
#    # update views for each row
#    row = 0
#    for model in self._model_list:
#      row_model = self.get_row_model(row)
#      if (row_model is not model):
#        self.set_row_model(row, model)
#      row += 1
#    # clear any remaining rows
#    rows = self.rowCount()
#    if (row < rows - 1):
#      for empty_row in range(row, rows):
#        self.clear_row(empty_row)
#    # add stretch at the end so the tracks have a fixed height
#    self.setRowStretch(rows, 1)
#  # get the model that's been placed at the given row index
#  def get_row_model(self, row):
#    row_item = self.itemAtPosition(row, 0)
#    if (row_item is None): return(None)
#    row_view = row_item.widget()
#    if (row_view is None): return(None)
#    return(row_view.model)
#  # set the model to place at the given row index
#  def set_row_model(self, row, track):
#    self.clear_row(row)
#    self.addWidget(PitchKeyView(track, view_scale=self.view_scale), row, 0)
#    self.addWidget(TrackView(track, 
#      view_scale=self.view_scale, 
#      margin=self._margin), row, 1)
#    self.setColumnStretch(1, 1)
#    self.setRowStretch(row, 0)
#  # remove all views at the given row
#  def clear_row(self, row):
#    rows = self.rowCount()
#    if (row >= rows): return
#    cols = self.columnCount()
#    for col in range(0, cols):
#      item = self.itemAtPosition(row, col)
#      if (item is not None):
#        self.removeItem(item)
#  # do layout of back and front views
#  def setGeometry(self, r):
#    QGridLayout.setGeometry(self, r)
#    trackColumn = self.cellRect(0, 1)
#    trackColumn.setHeight(r.height())
#    if (trackColumn is not None):
#      self.front_view.setGeometry(trackColumn)
#      self.front_view.raise_()

## make a view to act as an overlay for a track list
#class TrackListFrontView(core.ModelView):
#  def __init__(self, tracks, transport, view_scale=None, parent=None, margin=1):
#    core.ModelView.__init__(self, model=tracks, parent=parent)
#    self.view_scale = view_scale
#    self.view_scale.add_observer(self.on_change)
#    self.transport = transport
#    self.transport.add_observer(self.on_change)
#    self._margin = margin
#    # this needs to be transparent for mouse events so it doesn't eat clicks
#    #  on the document itself
#    self.setAttribute(Qt.WA_TransparentForMouseEvents)
#  def redraw(self, qp, width, height):
#    x = self._margin + self.view_scale.x_of_time(self.transport.time)
#    qp.setBrush(self.brush(0.10))
#    qp.drawRect(0, 0, x, height)
#    pen = QPen(QColor(255, 0, 0, 128))
#    pen.setWidth(2)
#    qp.setPen(pen)
#    qp.drawLine(x, 0, x, height)
    
# make a view that displays a list of tracks
class TrackListView(core.BoxSelectable, core.Interactive, core.ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None):
    core.ModelView.__init__(self, model=tracks, parent=parent)
    core.Interactive.__init__(self)
    core.BoxSelectable.__init__(self)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.transport = transport
    self.track_layout = core.VBoxLayout(self, tracks,
      lambda t: TrackView(t, view_scale=view_scale))
  def paint(self, qp, options, widget):
    width = self._size.width()
    height = self._size.height()
    qp.setBrush(QBrush(QColor(255, 0, 0)))
    qp.drawRect(0, 0, width, height)
    self.track_layout.setRect(QRectF(0, 0, width, height))
  
  # clear the selection when clicked
  def on_click(self, event):
    if (event.modifiers() == 0):
      doc.Selection.deselect_all()
  @property
  def track(self):
    return(self._model)

class TrackLayout(core.ListLayout):
  @property
  def track(self):
    return(self._items)
  def layout(self):
    y = self._rect.y()
    for view in self._views:
      x = view.model.time
      try:
        w = view.model.duration
      except AttributeError:
        w = view.rect().width()
      view.setRect(QRectF(x, y, w, len(self.track.pitches)))

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
    
  def on_scale(self):
    t = QTransform()
    t.scale(self.view_scale.pixels_per_second, self.view_scale.pitch_height)
    self.block_layout.setTransform(t)
    
  def rect(self):
    r = core.ModelView.rect(self)
    r.setHeight(len(self.track.pitches) * self.view_scale.pitch_height)
    return(r)

  def paint(self, qp, options, widget):
    r = self.rect()
    width = r.width()
    height = r.height()
    qp.setBrush(QBrush(QColor(0, 0, 255)))
    qp.drawRect(0, 0, width, height)
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

