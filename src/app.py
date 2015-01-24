#!/usr/bin/env python

import sys
import os
import platform

from PySide.QtCore import *
from PySide.QtGui import *

from jackdaw import windows, track, block, doc, sampler

class App(QApplication):
  def __init__(self):
    QApplication.__init__(self, sys.argv)
    self._window = windows.DocumentWindow(self)
    self._window.show()
    # open test file for rapid debugging
    if (platform.node() == 'boombox.home.net'):
      test_path = '/home/jesse/Documents/test.jdp'
      if (os.path.exists(test_path)):
        self._window.document = doc.Document.get_from_path(test_path)
    if (self._window.document is None):
      self._window.document = doc.Document()
    # start the sampler engine
    sampler.LinuxSampler.start()

app = App()
sys.exit(app.exec_())
