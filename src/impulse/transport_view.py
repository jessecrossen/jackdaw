import os
import math

from PySide.QtCore import *
from PySide.QtGui import *

import transport
import view
import unit_view

# an overlay for a track list that shows the state of the transport
class TransportView(view.ModelView):
  def __init__(self, transport, view_scale=None, parent=None):
    view.ModelView.__init__(self, model=transport, parent=parent)
    self.transport.add_observer(self.check_bounds)
    self.time_layout = TransportLayout(transport=self.transport, parent=self)
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_scale)
    self.on_scale()
  def destroy(self):
    self.view_scale.remove_observer(self.update)
    self.transport.remove_observer(self.check_bounds)
    view.ModelView.destroy(self)
  @property
  def transport(self):
    return(self._model)
  # respond to scaling
  def on_scale(self):
    t = QTransform()
    t.scale(self.view_scale.pixels_per_second, 1.0)
    t.translate(- self.view_scale.time_offset, 0)
    self.time_layout.setTransform(t)
  # make sure the transport stays visible
  def check_bounds(self):
    pps = self.view_scale.pixels_per_second
    r = self.rect()
    current_time = self.transport.time
    # get the range of time shown by this view
    time_shown = r.width() / pps
    start_time = self.view_scale.time_offset
    end_time = start_time + time_shown
    # if the transport goes off the edge, scroll to show it
    margin_time = 20.0 / pps
    if (end_time - start_time < (margin_time * 2.0)):
      self.view_scale.time_offset = (start_time + end_time) / 2.0
    elif (current_time < start_time + margin_time):
      self.view_scale.time_offset = max(0.0, 
        current_time - margin_time)
    elif (current_time > end_time - margin_time):
      self.view_scale.time_offset = max(0.0, 
        current_time + margin_time - time_shown)
  # do layout
  def layout(self):
    r = self.rect()
    self.time_layout.setRect(QRectF(0.0, 0.0, r.width(), r.height()))

class TransportLayout(view.ModelView):
  def __init__(self, transport, parent=None):
    view.ModelView.__init__(self, model=transport, parent=parent)
    # darken slightly before the current time so it's easier to find 
    #  the timepoint
    self.passed_time_view = PassedTimeView(
        transport=self.transport, parent=self)
    # draw the current time
    time_brush = QBrush(QColor(255, 0, 0, 128))
    self.current_time_view = TimepointView(
      model=self.transport, brush=time_brush, parent=self)
    # draw marks
    color = self.palette.color(QPalette.Normal, QPalette.WindowText)
    color.setAlphaF(0.85)
    mark_brush = QBrush(color, Qt.Dense4Pattern)
    self.marks_layout = MarksLayout(self, self.transport.marks, 
      lambda m: TimepointView(model=m, brush=mark_brush))
  @property
  def transport(self):
    return(self._model)
  def layout(self):
    r = self.rect()
    height = r.height()
    self.passed_time_view.setRect(QRectF(
      0.0, 0.0, self.transport.time, height))
    self.current_time_view.setRect(QRectF(
      self.transport.time, 0.0, 0.0, height))
    self.marks_layout.setRect(QRectF(0.0, 0.0, 0.0, height))

# represent the time which has passed so far in the transport
class PassedTimeView(view.ModelView):
  def __init__(self, transport, parent=None):
    view.ModelView.__init__(self, model=transport, parent=parent)
  def paint(self, qp, options, width):
    r = self.rect()
    qp.setBrush(self.brush(0.05))
    qp.setPen(Qt.NoPen)
    qp.drawRect(QRectF(0.0, 0.0, r.width(), r.height()))

# represent a timepoint on a transit
class TimepointView(view.TimeDraggable, view.ModelView):
  def __init__(self, model, brush=Qt.NoBrush, parent=None):
    self._brush = brush
    view.ModelView.__init__(self, model=model, parent=parent)
    view.TimeDraggable.__init__(self)
    self.setCursor(Qt.SizeHorCursor)
  def boundingRect(self):
    r = self.mapRectFromScene(QRectF(0.0, 0.0, 1.0, 0.0))
    px = r.width()
    return(QRectF(- 2.0 * px, 0.0, 4.0 * px, self.rect().height()))
  def paint(self, qp, options, width):
    t = qp.deviceTransform()
    px = 1.0 / t.m11()
    qp.setBrush(self._brush)
    qp.setPen(Qt.NoPen)
    qp.drawRect(QRectF(- px, 0.0, 2.0 * px, self.rect().height()))

# do layout of marks on a transport
class MarksLayout(view.ListLayout):
  def __init__(self, *args, **kwargs):
    view.ListLayout.__init__(self, *args, **kwargs)
  def layout(self):
    y = self._rect.y()
    h = self._rect.height()
    for view in self._views:
      view.setRect(QRectF(view.model.time, y, 0.0, h))

# make a view that displays transport controls
class TransportControlView(view.ModelView):
  def __init__(self, transport, parent=None):
    view.ModelView.__init__(self, model=transport, parent=parent)
    self.button_size = 30
    self.begin_button = None
    self.back_button = None
    self.forward_button = None
    self.end_button = None
    self.stop_button = None
    self.play_button = None
    self.record_button = None
    self.cycle_button = None
    self.button_proxies = list()
  @property
  def transport(self):
    return(self._model)
  def minimumSizeHint(self):
    s = self.button_size
    return(QSizeF(4 * s, 2 * s))
  # add a proxied button widget and return it
  def add_button(self, icon):
    button = QPushButton()
    button.setIcon(QIcon.fromTheme(icon))
    button.setFocusPolicy(Qt.NoFocus)
    proxy = self.scene().addWidget(button)
    proxy.setParentItem(self)
    self.button_proxies.append(proxy)
    return(button)
  def layout(self):
    if (not self.scene()): return
    # make buttons
    if (not self.begin_button):
      self.begin_button = self.add_button('media-skip-backward')
      self.begin_button.clicked.connect(self.transport.go_to_beginning)
    if (not self.back_button):
      self.back_button = self.add_button('media-seek-backward')
      self.back_button.clicked.connect(self.transport.skip_back)
    if (not self.forward_button):
      self.forward_button = self.add_button('media-seek-forward')
      self.forward_button.clicked.connect(self.transport.skip_forward)
    if (not self.end_button):
      self.end_button = self.add_button('media-skip-forward')
      self.end_button.clicked.connect(self.transport.go_to_end)
    if (not self.stop_button):
      self.stop_button = self.add_button('media-playback-stop')
      self.stop_button.clicked.connect(self.transport.stop)
    if (not self.play_button):
      self.play_button = self.add_button('media-playback-start')
      self.play_button.clicked.connect(self.transport.play)
    if (not self.record_button):
      self.record_button = self.add_button('media-record')
      self.record_button.clicked.connect(self.transport.record)
    if (not self.cycle_button):
      self.cycle_button = self.add_button('view-refresh')
      self.cycle_button.setCheckable(True)
      self.cycle_button.toggled.connect(self.on_cycle)
    if (self.cycle_button):
      self.cycle_button.setChecked(self.transport.cycling)
    # do layout of buttons
    r = self.rect()
    width = r.width()
    height = r.height()
    size = self.button_size
    if (len(self.button_proxies) > 0):
      x = 0.0
      y = 0.0
      for proxy in self.button_proxies:
        button = proxy.widget()
        button.setFixedWidth(size)
        button.setFixedHeight(size)
        proxy.setPos(QPointF(x, y))
        x += size
        if (x >= r.width()):
          x = 0
          y += size
  # handle button actions not implemented directly by the transport
  def on_cycle(self, toggled):
    self.transport.cycling = toggled

# make a unit view that represents a transport on the workspace
class TransportUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._content = TransportControlView(transport=self.unit.transport)
    self._content.setParentItem(self)
    # add an input so the transport can be controlled via midi
    self._input_layout = unit_view.InputListLayout(self, list((self.unit.transport,)), 
                                         lambda t: unit_view.UnitInputView(t))
    # allow the user to remove the unit
    self.allow_delete = True
  def layout(self):
    size = self._content.minimumSizeHint()
    self._content.setRect(QRectF(0, 0, size.width(), size.height()))
    unit_view.UnitView.layout(self)
# register the view for placement on the workspace
unit_view.UnitView.register_unit_view(
  transport.TransportUnit, TransportUnitView)