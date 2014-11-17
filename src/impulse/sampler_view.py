import math

from PySide.QtCore import *
from PySide.QtGui import *

import view

# make a view that displays a list of sampler instruments
class InstrumentListView(view.ModelView):
  def __init__(self, instruments, require_input=False, require_output=False, 
                     parent=None):
    view.ModelView.__init__(self, model=instruments, parent=parent)
    self.require_input = require_input
    self.require_output = require_output
    self.instrument_layout = view.VBoxLayout(self, instruments, 
      lambda i: InstrumentView(i))
    self.instrument_layout.spacing = 6.0
  @property
  def instruments(self):
    return(self._model)
  def minimumSizeHint(self):
    w = 120; h = 0
    for view in self.instrument_layout.views:
      s = view.minimumSizeHint()
      w = max(w, s.width())
      h += s.height() + self.instrument_layout.spacing
    return(QSizeF(w, h))
  def layout(self):
    self.instrument_layout.setRect(self.boundingRect())

# make a view that displays a sampler instrument
class InstrumentView(view.NamedModelView):
  def __init__(self, instrument, parent=None):
    view.NamedModelView.__init__(self, model=instrument, parent=parent)
  @property
  def instrument(self):
    return(self._model)
