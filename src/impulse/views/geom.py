from gi.repository import Gdk

class Rectangle(Gdk.Rectangle):
  def __new__(cls, x=0, y=0, width=0, height=0):
    r = Gdk.Rectangle.__new__(cls)
    r.x = x
    r.y = y
    r.width = width
    r.height = height
    return(r)
  # make a friendlier display of the rectangle
  def __repr__(self):
    return('Rectangle(%d, %d, %d, %d)' % 
            (self.x, self.y, self.width, self.height))
  # return whether the rectangle contains the given point
  def contains(self, x, y):
    return((x >= self.x) and (x <= self.x + self.width) and
           (y >= self.y) and (y <= self.y + self.height))

class Point(Gdk.Point):
  def __new__(cls, x=0, y=0):
    p = Gdk.Point.__new__(cls)
    p.x = x
    p.y = y
    return(p)
  # make a friendlier display of the point
  def __repr__(self):
    return('Point(%d, %d)' % (self.x, self.y))
