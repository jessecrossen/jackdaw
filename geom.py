from gi.repository import Gdk

class Rectangle(Gdk.Rectangle):
  def __init__(self, x=0, y=0, width=0, height=0):
    Gdk.Rectangle.__init__(self)
    self.x = x
    self.y = y
    self.width = width
    self.height = height
  # make a friendlier display of the rectangle
  def __str__(self):
    return('Rectangle(%.1f, %.1f, %.1f, %.1f)' % 
            (self.x, self.y, self.width, self.height))
  # return whether the rectangle contains the given point
  def contains(self, x, y):
    return((x >= self.x) and (x <= self.x + self.width) and
           (y >= self.y) and (y <= self.y + self.height))
