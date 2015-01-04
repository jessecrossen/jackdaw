#!/usr/bin/env python

import sys
import platform

from PySide.QtCore import *
from PySide.QtGui import *

from impulse import windows, track, block, doc, sampler

class App(QApplication):
  def __init__(self):
    QApplication.__init__(self, sys.argv)
    self._window = windows.DocumentWindow(self)
    self._window.show()
    # open test file for rapid debugging
    if (platform.node() == 'boombox.home.net'):
      self._window.document = doc.Document.get_from_path(
        '/home/jesse/Documents/impulse/test.jdp')
    # start the sampler engine
    sampler.LinuxSampler.start()

app = App()
sys.exit(app.exec_())
