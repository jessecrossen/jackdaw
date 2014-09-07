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
  def __init__(self, tracks, parent=None, view_scale=None):
    QGridLayout.__init__(self, parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # attach to the list of models
    self._model_list = tracks
    self._model_list.add_observer(self.on_change)
    self.update_views()
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
    self.addWidget(TrackView(track, view_scale=self.view_scale), row, 0)
  # remove all views at the given row
  def clear_row(self, row):
    rows = self.rowCount()
    if (row >= rows): return
    cols = self.columnCount()
    for col in range(0, cols):
      item = self.itemAtPosition(row, col)
      if (item is not None):
        self.removeItem(item)

# make a view that displays a list of tracks
class TrackListView(ModelView):
  def __init__(self, tracks, view_scale=None, parent=None):
    ModelView.__init__(self, model=tracks, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # add a layout for the tracks
    self.layout = TrackListLayout(
      tracks, view_scale=self.view_scale)
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
  def __init__(self, track, view_scale=None, parent=None):
    ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # add a layout for the blocks
    self.layout = TrackLayout(
      track, view_scale=self.view_scale)
    self.setLayout(self.layout)
  
  @property
  def track(self):
    return(self._model)

  def redraw(self, qp, width, height):
    pen = QPen(QColor(20, 20, 20), 1, Qt.SolidLine)
    qp.setPen(pen)
    qp.drawLine(0, 0, width, height)

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

