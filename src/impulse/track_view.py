import math

from PySide.QtCore import *
from PySide.QtGui import *

import track
import view
from doc import ViewScale
from model import Selection
from undo import UndoManager
from block_view import BlockView
import unit_view
import transport_view

# make a view that displays a list of tracks
class TrackListView(view.BoxSelectable, view.Interactive, view.ModelView):
  def __init__(self, tracks, transport, view_scale=None, parent=None):
    view.ModelView.__init__(self, model=tracks, parent=parent)
    view.Interactive.__init__(self)
    view.BoxSelectable.__init__(self)
    self.scrollbar_proxy = None
    self.scrollbar = None
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.view_scale.add_observer(self.update_scrollbar)
    self.transport = transport
    self.toggle_layout = view.VBoxLayout(self, tracks,
      lambda t: TrackToggleView(t, view_scale=view_scale))
    self.pitch_key_layout = view.VBoxLayout(self, tracks,
      lambda t: PitchKeyView(t, view_scale=view_scale))
    self.track_layout = view.VBoxLayout(self, tracks,
      lambda t: TrackView(t, view_scale=view_scale))
    self.pitch_key_layout.spacing = self.view_scale.track_spacing
    self.track_layout.spacing = self.view_scale.track_spacing
    # add a view for the transport
    self.overlay = transport_view.TransportView(
      transport=self.transport,
      view_scale=self.view_scale,
      parent=self)
  @property
  def tracks(self):
    return(self._model)
  # return the minimum size of all tracks and controls
  def minimumSizeHint(self):
    w = h = 0
    w += self.pitch_key_width()
    w += self.toggle_width()
    for track in self.tracks:
      h += self.view_scale.height_of_track(track)
      h += self.view_scale.track_spacing
    if (self.scrollbar):
      h += self.scrollbar.size().height()
    return(QSizeF(w * 2, h))
  def pitch_key_width(self):
    w = 30
    for view in self.pitch_key_layout.views:
      w = max(w, view.minimumSizeHint().width())
    return(w)
  def toggle_width(self):
    return(self.view_scale.pitch_height)
  def layout(self):
    width = self._size.width()
    height = self._size.height()
    x = 0
    w = self.toggle_width()
    self.toggle_layout.setRect(QRectF(x, 0, w, height))
    x += w + (self.view_scale.track_spacing / 2)
    w = self.pitch_key_width()
    self.pitch_key_layout.setRect(QRectF(x, 0, w, height))
    x += w + (self.view_scale.track_spacing / 2)
    # add a scrollbar to scroll through the timeline
    if ((not self.scrollbar) and (self.scene())):
      self.scrollbar = QScrollBar(Qt.Orientation.Horizontal)
      self.scrollbar.valueChanged.connect(self.on_scroll)
      self.scrollbar_proxy = self.scene().addWidget(self.scrollbar)
      self.scrollbar_proxy.setParentItem(self)
    if (self.scrollbar):
      # position the scrollbar
      g = self.scrollbar.geometry()
      height -= g.height()
      self.scrollbar.setGeometry(0, height, width, g.height())
    self.update_scrollbar()
    # position the tracks and transport so as not to overlap the scrollbar
    r = QRectF(x, 0, width - x, height)
    self.track_layout.setRect(r)
    self.overlay.setRect(r)
  def update_scrollbar(self):
    if (not self.scrollbar): return
    try:
      width = self.track_layout.rect().width()
    except AttributeError:
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
    self.scrollbar.setValue(int(self.view_scale.time_offset * 1000))
  # handle scrolling
  def on_scroll(self):
    time = float(self.scrollbar.value()) / 1000.0
    self.view_scale.time_offset = time
  # clear the selection when clicked
  def on_click(self, event):
    if (event.modifiers() == 0):
      Selection.deselect_all()
  @property
  def track(self):
    return(self._model)

# do layout of blocks in a track
class TrackLayout(view.ListLayout):
  def __init__(self, *args, **kwargs):
    view.ListLayout.__init__(self, *args, **kwargs)
  @property
  def track(self):
    return(self._items)
  # clip so that blocks scrolled off the view will not be shown
  def clipRect(self):
    return(self.boundingRect())
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
class TrackView(view.ModelView):
  def __init__(self, track, view_scale=None, parent=None):
    view.ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_scale)
    # add a layout for the blocks
    self.block_layout = TrackLayout(self, track, 
      lambda b: BlockView(b, track=track))
    self.on_scale()
  def destroy(self):
    self.view_scale.remove_observer(self.on_scale)
    view.ModelView.destroy(self)
  @property
  def track(self):
    return(self._model)
  # respond to scaling
  def on_scale(self):
    t = QTransform()
    t.scale(self.view_scale.pixels_per_second, 
                        self.view_scale.pitch_height)
    t.translate(- self.view_scale.time_offset, 0)
    self.block_layout.setTransform(t)
    # force all blocks to update their layouts to handle 
    #  scale-dependent geometry and/or clipping changes
    self.block_layout.layout()
    for view in self.block_layout.views:
      if (view.isVisible()):
        view.layout()
  # provide a height for layout in the parent
  def rect(self):
    r = view.ModelView.rect(self)
    r.setHeight(self.view_scale.height_of_track(self.track))
    return(r)
  # update the placement of the layout
  def _paint(self, qp):
    r = self.rect()
    width = r.width()
    height = r.height()
    # draw a background depending on track state
    background = None
    block_opacity = 1.0
    if (self.track.arm):
      background = QColor(255, 0, 0)
      block_opacity = 0.75
    elif (not self.track.enabled):
      background = self.palette.color(QPalette.Normal, QPalette.WindowText)
      block_opacity = 0.50
    if (background is not None):
      qp.setPen(Qt.NoPen)
      background.setAlphaF(0.25)
      qp.setBrush(QBrush(background))
      qp.drawRect(QRectF(0.0, 0.0, width, height))
    # position the block layout
    self.block_layout.setRect(QRectF(0, 0, width, height))
    # dim the block layout when muted
    self.block_layout.setOpacity(block_opacity)

# a view to show arm/mute/solo buttons for the track
class TrackToggleView(view.ModelView):
  def __init__(self, track, view_scale, parent=None):
    view.ModelView.__init__(self, model=track, parent=parent)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.update)
    self.spacing = 4
    self.arm_button = None
    self.mute_button = None
    self.solo_button = None
    self.button_proxies = list()
  def rect(self):
    r = view.ModelView.rect(self)
    r.setHeight(self.view_scale.height_of_track(self.track))
    return(r)
  def layout(self):
    if (not self.scene()): return
    r = self.rect()
    width = r.width()
    height = r.height()
    # make a view for the track name
    if (not self.arm_button):
      self.arm_button = self.add_button('R')
      self.arm_button.setChecked(self.track.arm)
      self.arm_button.toggled.connect(self.on_arm)
      self.arm_button.setStyleSheet('''
        * { font-size: 12px }
        *:checked {
          background: red;
          color: white;
          font-weight: bold;
        }
      ''')
    if (not self.mute_button):
      self.mute_button = self.add_button('M')
      self.mute_button.setChecked(self.track.mute)
      self.mute_button.toggled.connect(self.on_mute)
      self.mute_button.setStyleSheet('''
        * { font-size: 12px }
        *:checked {
          background: rgba(0, 0, 0, 192);
          color: white;
          font-weight: bold;
        }
      ''')
    if (not self.solo_button):
      self.solo_button = self.add_button('S')
      self.solo_button.setChecked(self.track.solo)
      self.solo_button.toggled.connect(self.on_solo)
      self.solo_button.setStyleSheet('''
        * { font-size: 12px }
        *:checked {
          background: yellow;
          font-weight: bold;
        }
      ''')
    # update button state
    self.arm_button.setChecked(self.track.arm)
    self.mute_button.setChecked(self.track.mute)
    self.solo_button.setChecked(self.track.solo)
    # position buttons in a vertically centered block
    num_buttons = len(self.button_proxies)
    buttons_height = (num_buttons * width) + ((num_buttons - 1) * self.spacing)
    y = round((height / 2.0) - (buttons_height / 2.0))
    for proxy in self.button_proxies:
      button = proxy.widget()
      button.setFixedHeight(width)
      button.setFixedWidth(width)
      proxy.setPos(QPointF(0.0, y))
      y += width + self.spacing
  # add a proxied button widget and return it
  def add_button(self, label):
    button = QPushButton()
    button.setText(label)
    button.setFlat(True)
    button.setCheckable(True)
    button.setFocusPolicy(Qt.NoFocus)
    proxy = self.scene().addWidget(button)
    proxy.setParentItem(self)
    self.button_proxies.append(proxy)
    return(button)
  # respond to buttons being toggled
  def on_arm(self, toggled):
    self.track.arm = toggled
  def on_mute(self, toggled):
    self.track.mute = toggled
  def on_solo(self, toggled):
    self.track.solo = toggled
  @property
  def track(self):
    return(self._model)

# show an editable label for a pitch on the track
class PitchNameView(view.EditableLabel):
  def __init__(self, track, pitch, parent=None):
    view.EditableLabel.__init__(self, parent)
    # link to the track and index
    self._track = track
    self._pitch = None
    self.pitch = pitch
    self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    self.textEdited.connect(self.on_edited)
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

# show a controller's name and cached value
class ControllerKeyView(view.ModelView):
  VALUE_WIDTH = 3
  def __init__(self, track, number, parent):
    self._name_view = None
    self._name_proxy = None
    self._number = number
    view.ModelView.__init__(self, track, parent)
  @property
  def track(self):
    return(self._model)
  @property
  def number(self):
    return(self._number)
  @number.setter
  def number(self, value):
    if (value != self._number):
      self._number = value
      self.update()
    if (self._name_view is not None):
      self._name_view.number = value
  def minimumSizeHint(self):
    if (self._name_view):
      size = self._name_view.minimumSizeHint()
      return(QSize(size.width(), size.height() + self.VALUE_WIDTH))
    return(QSize(0, 0))
  def layout(self):
    if (not self.scene()): return
    if (not self._name_view):
      self._name_view = ControllerNameView(track=self.track, number=self.number)
      self._name_view.editingFinished.connect(self.parentItem().request_resize)
      self._name_proxy = self.scene().addWidget(self._name_view)
      self._name_proxy.setParentItem(self)
    r = self.rect()
    self._name_proxy.widget().setFixedHeight(r.height())
    self._name_proxy.widget().setGeometry(
      QRect(0, 0, r.width() - self.VALUE_WIDTH, r.height()))
  def _paint(self, qp):
    r = self.rect()
    width = r.width()
    height = r.height()
    value = self.track.value_of_controller(self.number)
    vw = self.VALUE_WIDTH
    if (value is not None):
      qp.setPen(Qt.NoPen)
      qp.setBrush(self.brush())
      y = 1 + ((height - vw - 2) * (1.0 - value))
      qp.drawRect(QRectF(width - vw, y, vw, vw))

# show an editable label for a controller number on the track
class ControllerNameView(view.EditableLabel):
  def __init__(self, track, number, parent=None):
    view.EditableLabel.__init__(self, parent)
    # link to the track and index
    self._track = track
    self._number = None
    self.number = number
    self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    self.textEdited.connect(self.on_edited)
  @property
  def number(self):
    return(self._number)
  @number.setter
  def number(self, value):
    if (value != self._number):
      self._number = value
      self._update_name()
  def _update_name(self):
    self.setText(self._track.name_of_controller(self._number))
  def on_edited(self, text):
    if (len(text) > 0):
      self._track.controller_names[self._number] = text
    else:
      try:
        del self._track.controller_names[self._number]
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
class PitchKeyView(view.ModelView):
  SPACING = 6.0
  def __init__(self, track, view_scale=None, parent=None):
    view.ModelView.__init__(self, model=track, parent=parent)
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    self.pitch_view_proxies = list()
    self.controller_views = list()
    self.track_name_proxy = None
  @property
  def track(self):
    return(self._model)
  # provide a height for layout in the parent
  def rect(self):
    r = view.ModelView.rect(self)
    r.setHeight(self.view_scale.height_of_track(self.track))
    return(r)
  def layout(self):
    if (not self.scene()): return
    height = self.rect().height()
    h = self.view_scale.pitch_height
    # make a view for the track name
    if (not self.track_name_proxy):
      self.track_name_proxy = self.scene().addWidget(view.NameLabel(self.track))
      self.track_name_proxy.setParentItem(self)
      self.track_name_proxy.setRotation(-90)
    name_view = self.track_name_proxy.widget()
    name_view.setFixedHeight(h)
    name_view.setFixedWidth(height)
    self.track_name_proxy.setPos(QPointF(0.0, height))
    # position the pitch names
    r = self.rect()
    x = h + self.SPACING
    y = 0
    i = 0
    for pitch in reversed(self.track.pitches):
      if (i < len(self.pitch_view_proxies)):
        proxy = self.pitch_view_proxies[i]
        proxy.widget().pitch = pitch
      else:
        name_view = PitchNameView(track=self.track, pitch=pitch)
        name_view.editingFinished.connect(self.request_resize)
        proxy = self.scene().addWidget(name_view)
        proxy.setParentItem(self)
        self.pitch_view_proxies.append(proxy)
      proxy.widget().setFixedHeight(h)
      proxy.widget().setGeometry(QRect(x, y, r.width() - x, h))
      y += h
      i += 1
    for i in range(len(self.track.pitches), len(self.pitch_view_proxies)):
      proxy = self.pitch_view_proxies.pop()
      self.scene().removeItem(proxy)
      proxy.setParentItem(None)
    # position the controller names
    h = self.view_scale.controller_height
    i = 0
    for number in self.track.controllers:
      if (i < len(self.controller_views)):
        controller_view = self.controller_views[i]
        controller_view.number = number
      else:
        controller_view = ControllerKeyView(track=self.track, number=number, parent=self)
        self.controller_views.append(controller_view)
      controller_view.setRect(QRect(x, y, r.width() - x, h))
      y += h
      i += 1
    for i in range(len(self.track.controllers), 
                   len(self.controller_views)):
      controller_view = self.controller_views.pop()
      controller_view.destroy()
  # suggest a minimum size that makes room for all the name views
  def minimumSizeHint(self):
    w = 0
    h = 0
    for proxy in self.pitch_view_proxies:
      s = proxy.widget().minimumSizeHint()
      w = max(w, s.width())
      h += s.height()
    for controller_view in self.controller_views:
      s = controller_view.minimumSizeHint()
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

# lay out all the output ports for a list of tracks
class TrackListOutputLayout(view.ListLayout):
  def __init__(self, parent, tracks, view_scale):
    self.view_scale = view_scale
    view.ListLayout.__init__(self, parent, tracks, 
                             lambda t: TrackOutputLayout(self, t, view_scale))
    self.view_scale.add_observer(self.layout)
  def destroy(self):
    self.view_scale.remove_observer(self.layout)
    view.ListLayout.destroy(self)
  def layout(self):
    r = self._rect
    x = self._rect.right() + unit_view.UnitPortView.OFFSET
    y = self._rect.y()
    spacing = self.view_scale.track_spacing
    for layout in self._views:
      layout.setPos(QPointF(x, y))
      y += self.view_scale.height_of_track(layout.track) + spacing
# lay out the output ports for a single track
class TrackOutputLayout(view.ListLayout):
  def __init__(self, parent, track, view_scale):
    self.track = track
    self.view_scale = view_scale
    self.note_output_view = unit_view.UnitOutputView(self.track)
    view.ListLayout.__init__(self, parent, (), 
                             lambda t: unit_view.UnitOutputView(t))
    self.note_output_view.setParentItem(self)
    self.track.add_observer(self.on_track_change)
    self.view_scale.add_observer(self.layout)
    self.on_track_change()
  def destroy(self):
    self.note_output_view.destroy()
    self.track.remove_observer(self.on_track_change)
    self.view_scale.remove_observer(self.layout)
    view.ListLayout.destroy(self)
  def on_track_change(self):
    self.items = tuple(self.track.controller_outputs)
  @property
  def items(self):
    return(self._items)
  @items.setter
  def items(self, value):
    if (value != self._items):
      self._items = value
      self.update_views()
  def layout(self):
    r = self._rect
    note_height = len(self.track.pitches) * self.view_scale.pitch_height
    # if there are no controllers to make room for, we can place the note output 
    #  in the middle of the track
    if (len(self._views) == 0):
      note_height = self.view_scale.height_of_track(self.track)
    self.note_output_view.setPos(QPointF(0.0, note_height / 2.0))
    y = note_height
    h = self.view_scale.controller_height
    y += (h / 2.0)
    for output_view in self._views:
      output_view.setPos(QPointF(0.0, y))
      y += h

# make a unit view containing a list of tracks
class SequencerUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._content = TrackListView(
            tracks=self.unit.tracks,
            transport=self.unit.transport, 
            view_scale=self.unit.view_scale)
    self._content.setParentItem(self)
    # add inputs and outputs to the track
    self._input_layout = unit_view.InputListLayout(self, self.unit.tracks,
      lambda t: unit_view.UnitInputView(t))
    self._output_layout = TrackListOutputLayout(
      self, self.unit.tracks, self._content.view_scale)
    self._input_layout.y_of_view = self.y_of_track_input
    # allow horizontal resizing
    self.allow_resize_width = True
    # allow tracks to be added
    self.allow_add = True
    # allow the set of tracks to be deleted
    self.allow_delete = True
    # connect for recording undo/redo
    if (self.unit.transport is not None):
      self.unit.transport.recording_will_start.connect(self.on_record_start)
      self.unit.transport.recording_stopped.connect(self.on_record_stop)
  def destroy(self):
    if (self.unit.transport is not None):
      self.unit.transport.recording_will_start.disconnect(self.on_record_start)
      self.unit.transport.recording_stopped.disconnect(self.on_record_stop)
  def on_record_start(self):
    UndoManager.begin_action(self.unit.tracks, group='record')
  def on_record_stop(self):
    UndoManager.end_action(group='record')
  def on_add(self):
    UndoManager.begin_action(self.unit.tracks)
    self.unit.tracks.add_track()
    UndoManager.end_action()
  def layout(self):
    size = self._content.minimumSizeHint()
    self.unit.width = max(size.width(), self.unit.width)
    self._content.setRect(QRectF(0, 0, self.unit.width, size.height()))
    unit_view.UnitView.layout(self)
  def y_of_track_input(self, rect, view, index, view_count):
    y = rect.y()
    scale = self._content.view_scale
    spacing = scale.track_spacing
    i = 0
    for track in self.unit.tracks:
      h = scale.height_of_track(track)
      if (i >= index):
        y += (h / 2.0)
        return(y)
      y += h + spacing
      i += 1
    return(y)
# register the view for placement on the workspace
unit_view.UnitView.register_unit_view(track.SequencerUnit, SequencerUnitView)