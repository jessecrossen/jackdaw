import os
import glob
import tempfile

from PySide.QtCore import *
from PySide.QtGui import *

_icons = dict()

def get(name):
  if (name in _icons):
    return(_icons[name])
  # get a path to the icon files
  iconpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                          'icons', name+'.svg')
  if (not os.path.exists(iconpath)): return(None)
  # get the main color of the current UI theme
  color = QApplication.palette().color(QPalette.Normal, QPalette.WindowText)
  hexcolor = '#%02x%02x%02x' % (color.red(), color.green(), color.blue())
  # encapsulate each icon file into a QIcon and attach it to this namespace
  (tmpfile, tmppath) = tempfile.mkstemp(suffix='.svg')
  iconfile = open(iconpath, 'r')
  svg = iconfile.read()
  iconfile.close()
  svg = svg.replace('#000000', hexcolor)
  os.write(tmpfile, svg)
  os.close(tmpfile)
  _icons[name] = QIcon(tmppath)
  return(_icons[name])