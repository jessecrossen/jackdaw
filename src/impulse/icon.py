import os
import glob

from PySide.QtCore import *
from PySide.QtGui import *

# get a path to the icon files
icon_glob = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                         'icons', '*.svg')
# encapsulate each icon file into a QIcon and attach it to this namespace
for path in glob.glob(icon_glob):
  (name, ext) = os.path.splitext(os.path.basename(path))
  globals()[name] = QIcon(path)