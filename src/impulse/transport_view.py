import os
import math

from PySide.QtCore import *
from PySide.QtGui import *

import transport
import view
import unit_view

# make a view that displays transport controls
class TransportView(view.ModelView):
  def __init__(self, transport, parent=None):
    view.ModelView.__init__(self, model=transport, parent=parent)
    self.button_size = 30
    self.stop_button = None
    self.play_button = None
    self.record_button = None
    self.button_proxies = list()
  @property
  def transport(self):
    return(self._model)
  def minimumSizeHint(self):
    s = self.button_size
    return(QSizeF(max(1, len(self.button_proxies)) * s, s))
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
    if (not self.stop_button):
      self.stop_button = self.add_button('media-playback-stop')
      self.stop_button.clicked.connect(self.transport.stop)
    if (not self.play_button):
      self.play_button = self.add_button('media-playback-start')
      self.play_button.clicked.connect(self.transport.play)
    if (not self.record_button):
      self.record_button = self.add_button('media-record')
      self.record_button.clicked.connect(self.transport.record)
    # do layout of buttons
    r = self.rect()
    width = r.width()
    height = r.height()
    if (len(self.button_proxies) > 0):
      width = width / len(self.button_proxies)
      x = 0
      for proxy in self.button_proxies:
        button = proxy.widget()
        button.setFixedWidth(width)
        button.setFixedHeight(height)
        proxy.setPos(QPointF(x, 0.0))
        x += width

# make a unit view that represents a transport on the workspace
class TransportUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._content = TransportView(transport=self.unit.transport)
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