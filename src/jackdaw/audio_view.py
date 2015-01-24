from PySide.QtCore import *
from PySide.QtGui import *

import audio
import view
import unit_view

# make a unit view containing a list of input devices
class SystemPlaybackUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self.input_view = unit_view.UnitInputView(model=self.unit)
    self.input_view.setParentItem(self)
  def layout(self):
    unit_view.UnitView.layout(self)
    r = self.boundingRect()
    self.input_view.setPos(QPointF(r.left() - unit_view.UnitPortView.OFFSET, 
                                   r.center().y()))
# register the view for placement on the workspace
unit_view.UnitView.register_unit_view(
  audio.SystemPlaybackUnit, SystemPlaybackUnitView)