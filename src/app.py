#!/usr/bin/env python

import sys

from PySide.QtCore import *
from PySide.QtGui import *

from impulse import windows, track, block, doc, sampler

class App(QApplication):
  def __init__(self):
    QApplication.__init__(self, sys.argv)
    self._window = windows.DocumentWindow(self)
    self._window.show()
    self._window.document = doc.Document()
    # start the sampler engine
    sampler.LinuxSampler.start()

app = App()
sys.exit(app.exec_())
