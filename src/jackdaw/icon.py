import os
import glob
import tempfile

from PySide.QtCore import *
from PySide.QtGui import *

_icons = dict()

def get(name, color=None):
  key = name
  if (color is not None):
    key += '-'+color.name()
  if (key in _icons):
    return(_icons[key])
  # get a path to the icon files
  iconpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                          'icons', name+'.svg')
  if (not os.path.exists(iconpath)): return(None)
  # get the main color of the current UI theme
  fg_color = QApplication.palette().color(QPalette.Normal, QPalette.WindowText)
  # encapsulate each icon file into a QIcon and attach it to this namespace
  (tmpfile, tmppath) = tempfile.mkstemp(suffix='.svg')
  iconfile = open(iconpath, 'r')
  svg = iconfile.read()
  iconfile.close()
  svg = svg.replace('#000000', fg_color.name())
  if (color is not None):
    svg = svg.replace('#ff0000', color.name())
  os.write(tmpfile, svg)
  os.close(tmpfile)
  _icons[key] = QIcon(tmppath)
  return(_icons[key])