import os
import math
import glob
import functools

from PySide.QtCore import *
from PySide.QtGui import *

import sampler
import view
import unit_view

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
  def contextMenuEvent(self, e):
    # clear focus from the text input so it can be changed if the 
    #  instrument changes
    if (self.name_proxy):
      name_view = self.name_proxy.widget()
      name_view.clearFocus()
    # show the menu
    list_view = self.parentItemWithClass(InstrumentListView)
    instrument_list = None if list_view is None else list_view.instruments
    document_view = self.parentItemWithAttribute('document')
    document = None if document_view is None else document_view.document
    menu = InstrumentMenu(parent=e.widget(),
                          instrument=self.instrument,
                          instrument_list=instrument_list,
                          document=document)
    menu.popup(e.screenPos())

# make a context menu for an instrument
class InstrumentMenu(QMenu):
  def __init__(self, instrument, instrument_list=None, document=None, parent=None):
    QMenu.__init__(self, parent)
    self.document = document
    self.instrument = instrument
    self.instrument_list = instrument_list
    if (len(self.instrument.path) > 0):
      (name, ext) = os.path.splitext(os.path.basename(self.instrument.path))
      search_dir = os.path.dirname(self.instrument.path)
      for path in glob.glob(os.path.join(search_dir, '*'+ext)):
        (name, ext) = os.path.splitext(os.path.basename(path))
        action = QAction(name, self)
        action.setEnabled(path != self.instrument.path)
        action.triggered.connect(functools.partial(self.on_change_path, path))
        self.addAction(action)
      self.addSeparator()
    action = QAction('Browse...', self)
    action.triggered.connect(self.on_browse)
    self.addAction(action)
    if (self.instrument_list):
      action = QAction('Remove', self)
      action.triggered.connect(self.on_remove)
      self.addAction(action)
  def on_change_path(self, path):
    view.ViewManager.begin_action(self.instrument)
    self.instrument.path = path
    view.ViewManager.end_action()
  def on_browse(self):
    view.ViewManager.begin_action(self.instrument)
    self.instrument.browse()
    view.ViewManager.end_action()
  def on_remove(self):
    view.ViewManager.begin_action((self.instrument_list, self.document))
    if (self.document is not None):
      self.document.patch_bay.remove_connections_for_unit(self.instrument)
    self.instrument_list.remove(self.instrument)
    view.ViewManager.end_action()

# make a unit view containing a list of sampler instruments
class InstrumentListUnitView(unit_view.UnitView):
  def __init__(self, *args, **kwargs):
    unit_view.UnitView.__init__(self, *args, **kwargs)
    self._content = InstrumentListView(
      instruments=self.unit.instruments)
    self._content.setParentItem(self)
    # add inputs and outputs for the instruments
    self._input_layout = unit_view.InputListLayout(self, self.unit.instruments, 
                                         lambda t: unit_view.UnitInputView(t))
    self._output_layout = unit_view.OutputListLayout(self, self.unit.instruments, 
                                           lambda t: unit_view.UnitOutputView(t))
    # allow the user to add instruments
    self.allow_add = True
    # allow the user to remove the unit
    self.allow_delete = True
  def on_add(self):
    instrument = sampler.Instrument.new_from_browse()
    if (instrument is None): return
    view.ViewManager.begin_action(self._content)
    self._content.instruments.append(instrument)
    view.ViewManager.end_action()
  def layout(self):
    size = self._content.minimumSizeHint()
    self._content.setRect(QRectF(0, 0, size.width(), size.height()))
    unit_view.UnitView.layout(self)
# register the view for placement on the workspace
unit_view.UnitView.register_unit_view(
  sampler.InstrumentListUnit, InstrumentListUnitView)