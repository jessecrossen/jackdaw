import math
import cairo

from PySide.QtCore import *
from PySide.QtGui import *

#import symbols
from core import ModelView, ModelListLayout, ViewManager
from ..models.doc import ViewScale
from ..models import doc
import block

# do layout of tracks
class TrackListLayout(QGridLayout):
  def __init__(self, tracks, transport, parent=None, view_scale=None, margin=1):
    QGridLayout.__init__(self, parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self._margin = margin
    self.transport = transport
    # attach to the list of models
    self._model_list = tracks
    self._model_list.add_observer(self.on_change)
    self.update_views()
    # make views to go behind and in front of the tracks
    self.back_view = TrackListBackView(self.tracks, 
      transport=self.transport,
      view_scale=self.view_scale,
      margin=margin)
    self.addWidget(self.back_view)
    self.front_view = TrackListFrontView(self.tracks, 
      transport=self.transport,
      view_scale=self.view_scale,
      margin=margin)
    self.addWidget(self.front_view)
  @property
  def tracks(self):
    return(self._model_list)
  def on_change(self):
    self.update_views()
  def update_views(self):
    if (not self._model_list): return
    # update views for each row
    row = 0
    for model in self._model_list:
      row_model = self.get_row_model(row)
      if (row_model is not model):
        self.set_row_model(row, model)
      row += 1
    # clear any remaining rows
    rows = self.rowCount()
    if (row < rows - 1):
      for empty_row in range(row, rows):
        self.clear_row(empty_row)
    # add stretch at the end so the tracks have a fixed height
    self.setRowStretch(rows, 1)
  # get the model that's been placed at the given row index
  def get_row_model(self, row):
    row_item = self.itemAtPosition(row, 0)
    if (row_item is None): return(None)
    row_view = row_item.widget()
    if (row_view is None): return(None)
    return(row_view.model)
  # set the model to place at the given row index
  def set_row_model(self, row, track):
    self.clear_row(row)
    self.addWidget(PitchKeyView(track, view_scale=self.view_scale), row, 0)
    self.addWidget(TrackView(track, 
      view_scale=self.view_scale, 
      margin=self._margin), row, 1)
    self.setColumnStretch(1, 1)
    self.setRowStretch(row, 0)
  # remove all views at the given row
  def clear_row(self, row):
    rows = self.rowCount()
    if (row >= rows): return
    cols = self.columnCount()
    for col in range(0, cols):
      item = self.itemAtPosition(row, col)
      if (item is not None):
        self.removeItem(item)
  # do layout of back and front views
  def setGeometry(self, r):
    QGridLayout.setGeometry(self, r)
    trackColumn = self.cellRect(0, 1)
    trackColumn.setHeight(r.height())
    if (trackColumn is not None):
      self.back_view.setGeometry(trackColumn)
      self.back_view.lower()
      self.front_view.setGeometry(trackColumn)
      self.front_view.raise_()

# make a view to act as a background for a track list
class TrackListBackView(ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None, margin=1):
    ModelView.__init__(self, model=tracks, parent=parent)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
    self.transport = transport
    self.transport.add_observer(self.on_change)
    self._margin = margin
  # clear the selection when clicked
  def mouseReleaseEvent(self, event):
    if (event.modifiers() == 0):
      doc.Selection.deselect_all()
# make a view to act as an overlay for a track list
class TrackListFrontView(ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None, margin=1):
    ModelView.__init__(self, model=tracks, parent=parent)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
    self.transport = transport
    self.transport.add_observer(self.on_change)
    self._margin = margin
    # this needs to be transparent for mouse events so it doesn't eat clicks
    #  on the document itself
    self.setAttribute(Qt.WA_TransparentForMouseEvents)
  def redraw(self, qp, width, height):
    x = self._margin + self.view_scale.x_of_time(self.transport.time)
    qp.setBrush(self.brush(0.10))
    qp.drawRect(0, 0, x, height)
    pen = QPen(QColor(255, 0, 0))
    pen.setWidth(2)
    qp.setPen(pen)
    qp.drawLine(x, 0, x, height)
    
# make a view that displays a list of tracks
class TrackListView(ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None):
    ModelView.__init__(self, model=tracks, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.transport = transport
    # add a layout for the tracks
    self.layout = TrackListLayout(tracks, 
      transport=self.transport, 
      view_scale=self.view_scale)
    self.setLayout(self.layout)
  @property
  def track(self):
    return(self._model)

# do layout of blocks by time
class TrackLayout(ModelListLayout):
  def __init__(self, track, view_scale, margin=1):
    ModelListLayout.__init__(self, track, view_class=block.BlockView)
    self._margin = margin
    self.view_scale = view_scale
    self.view_scale.add_observer(self.invalidate)
  def destroy(self):
    self.view_scale.remove_observer(self.invalidate)
    ModelListLayout.destroy(self)
  @property
  def track(self):
    return(self._model_list)
  # recommend a size
  def sizeHint(self):
    return(self.minimumSize())
  def minimumSize(self):
    return(QSize(
      int(self.view_scale.x_of_time(self.track.duration) + (self._margin * 2)),
      int(self.view_scale.pitch_height * len(self.track.pitches))))
  # get the x coordinate for a given time
  def x_of_time(self, time):
    return(self._margin + 
      self.view_scale.x_of_time(time - self.view_scale.time_offset))
  # get a block view for the model
  def get_view_for_model(self, model):
    return(block.BlockView(model, 
      track=self.track, 
      view_scale=self.view_scale))
  # lay out items by time and duration
  def do_layout(self):
    rect = self.geometry()
    for view in self.views:
      model = view.model
      x1 = rect.x() + self.x_of_time(model.time) - self._margin
      x2 = rect.x() + self.x_of_time(model.time + model.duration) + self._margin
      view.setGeometry(QRect(x1, rect.y(), x2 - x1, rect.height()))

class TrackView(ModelView):
  def __init__(self, track, view_scale=None, parent=None, margin=1):
    ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # add a layout for the blocks
    self.layout = TrackLayout(track, 
      view_scale=self.view_scale, 
      margin=margin)
    self.setLayout(self.layout)
  @property
  def track(self):
    return(self._model)

# show a label for a pitch on the track
class PitchNameView(QLineEdit):
  def __init__(self, track, pitch, parent=None):
    QLineEdit.__init__(self, parent)
    # link to the track and index
    self._track = track
    self._pitch = None
    self.pitch = pitch
    # draw with no frame and a transparent background
    self.setFrame(False)
    p = self.palette()
    p.setBrush(QPalette.Base, Qt.NoBrush)
    self.setPalette(p)
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
    self.updateGeometry()
  def on_edit_finished(self):
    self._update_name()
  def sizeHint(self):
    return(self.minimumSizeHint())
  def minimumSizeHint(self):
    s = QLineEdit.sizeHint(self)
    fm = QFontMetrics(self.font())
    s.setWidth(fm.width('  '+self.text()))
    return(s)

# do layout for the pitches of a track
class PitchKeyLayout(QVBoxLayout):
  def __init__(self, track, view_scale, parent=None):
    QVBoxLayout.__init__(self, parent)
    self.view_scale = view_scale
    # attach to the track
    self._track = track
    self._track.add_observer(self.on_change)
    self.setSpacing(0)
    self.setContentsMargins(0, 0, 0, 0)
    self.update_views()
    # add some stretch at the end so the labels have a truly fixed height
    self.addStretch(1)
  @property
  def track(self):
    return(self._track)
  def on_change(self):
    self.update_views()
  def update_views(self):
    if (not self._track): return
    i = 0
    last = None
    for pitch in reversed(self._track.pitches):
      item = self.itemAt(i)
      if ((item is None) or (item.widget() is None)):
        name_view = PitchNameView(self._track, pitch)
        self.insertWidget(i, name_view)
      else:
        name_view = item.widget()
      name_view.pitch = pitch
      name_view.setFixedHeight(self.view_scale.pitch_height)
      if ((self.parentWidget() is not None) and (last is not None)):
        QWidget.setTabOrder(last, name_view)
      last = name_view
      i += 1
    count = self.count()
    unused = list()
    if (i < count):
      for j in range(i, count):
        widget = self.itemAt(j).widget()
        if (widget):
          unused.append(widget)
    for widget in unused:
       self.removeWidget(widget)
       widget.setParent(None)
# show names for the pitches on a track
class PitchKeyView(ModelView):
  def __init__(self, track, view_scale=None, parent=None):
    ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # add a layout for the pitches
    self.layout = PitchKeyLayout(
      track, view_scale=self.view_scale)
    self.setLayout(self.layout)

## display pitch names for a track
#class PitchKeyView(LayoutView):
#  def __init__(self, track):
#    LayoutView.__init__(self, track)
#    self.make_interactive()
#    self._labels = dict()
#    self.set_size_request(30, 80)
#    self.entry = Gtk.Entry()
#    self.entry.set_alignment(1.0)
#    self.entry.connect('changed', self.on_edit)
#    self.entry.connect('focus-out-event', self.on_end_edit)
#    self._editing_pitch = None
#    self.editable_area = geom.Rectangle()
#    self.cursor_areas[self.editable_area] = Gdk.Cursor.new(
#      Gdk.CursorType.XTERM)
#  # expose 'track' as an alternate name for 'model' for readability
#  @property
#  def track(self):
#    return(self._model)
#  # lay out the pitch labels
#  def layout(self, width, height):
#    # get a view for the track that has pitches
#    track_view = ViewManager.view_for_model(self._model, TrackView)
#    # save old entries
#    old_labels = dict(self._labels)
#    # draw the pitch labels
#    ty = 0
#    if (track_view):
#      ty = (height - track_view._height) / 2
#      h = track_view.pitch_height
#      max_width = 0
#      for pitch in self.track.pitches:
#        y = track_view.y_of_pitch(pitch)
#        # make an entry widget for the pitch
#        if (pitch in self._labels):
#          label = self._labels[pitch]
#          del old_labels[pitch]
#        else:
#          label = Gtk.Label()
#          label.set_alignment(1.0, 0.5)
#          self._labels[pitch] = label
#          self.add(label)
#        if (y is None): continue
#        y = y + ty - math.floor(h / 2)
#        name = self.track.name_of_pitch(pitch)
#        label.set_text(name)
#        r = geom.Rectangle(0, y, width, h)
#        (minimum_size, preferred_size) = label.get_preferred_size()
#        max_width = max(max_width, preferred_size.width)
#        label.size_allocate(r)
#        if (pitch == self._editing_pitch):
#          self.entry.size_allocate(r)
#      # remove unused entry widgets
#      for (pitch, label) in old_labels.iteritems():
#        label.destroy()
#        del self._labels[pitch]
#      # update the editable area
#      self.editable_area.width = width
#      self.editable_area.y = ty
#      self.editable_area.height = track_view._height
#      # request the size of the widest label
#      self.set_size_request(max_width + 12, -1)
#  # activate the entry when a pitch is clicked
#  def on_click(self, x, y, state):
#    for (pitch, label) in self._labels.iteritems():
#      r = label.get_allocation()
#      if ((y >= r.y) and (y <= r.y + r.height)):
#        if (self._editing_pitch is not None):
#          self.on_end_edit()
#        self.add(self.entry)
#        self.entry.size_allocate(r)
#        self.entry.set_text(self.track.name_of_pitch(pitch))
#        self.entry.grab_focus()
#        self._editing_pitch = pitch
#  # respond to a text entry being edited
#  def on_edit(self, *args):
#    # update the track's pitch-to-name map
#    if (self._editing_pitch is not None):
#      ViewManager.begin_action(self.track, 1000)
#      name = self.entry.get_text()
#      if (len(name) > 0):
#        self.track.pitch_names[self._editing_pitch] = name
#      # if the user erases the pitch name, 
#      #  revert to the default one
#      elif (self._editing_pitch in self.track.pitch_names):
#        del self.track.pitch_names[self._editing_pitch]
#      self.track.on_change()
#  # stop editing when the entry loses focus
#  def on_end_edit(self, *args):
#    if (self._editing_pitch is not None):
#      self._editing_pitch = None
#      self.remove(self.entry)

