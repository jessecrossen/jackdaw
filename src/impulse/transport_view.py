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
    # draw marked times on the transport
    color = self.palette.color(QPalette.Normal, QPalette.WindowText)
    color.setAlphaF(0.5)
    pen = QPen(color)
    pen.setCapStyle(Qt.FlatCap)
    pen.setWidth(2)
    pen.setDashPattern((2, 3))
    qp.setPen(pen)
    for mark in self.transport.marks:
      x = round((mark - self.view_scale.time_offset) * pps)
      qp.drawLine(QPointF(x, 0.0), QPointF(x, height))
    # draw the current timepoint in red
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
      self.begin_button.clicked.connect(self.on_begin)
    if (not self.back_button):
      self.back_button = self.add_button('media-seek-backward')
      self.back_button.clicked.connect(self.transport.skip_back)
    if (not self.forward_button):
      self.forward_button = self.add_button('media-seek-forward')
      self.forward_button.clicked.connect(self.transport.skip_forward)
    if (not self.end_button):
      self.end_button = self.add_button('media-skip-forward')
      self.end_button.clicked.connect(self.on_end)
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
  def on_begin(self):
    self.transport.time = 0.0
  def on_end(self):
    # TODO
    self.transport.time = 0.0
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