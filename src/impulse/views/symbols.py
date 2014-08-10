import cairo
import math

from core import geom

RADIUS = 4
BRACKET_WIDTH = (2 * RADIUS)
BRACKET_HEIGHT = (8 * RADIUS)

# draw a rounded rectangle
def draw_round_rect(cr, x, y, w, h, r):
  degrees = math.pi / 180.0
  cr.new_sub_path()
  cr.arc(x + w - r, y + r, r, -90 * degrees, 0 * degrees)
  cr.arc(x + w - r, y + h - r, r, 0 * degrees, 90 * degrees)
  cr.arc(x + r, y + h - r, r, 90 * degrees, 180 * degrees)
  cr.arc(x + r, y + r, r, 180 * degrees, 270 * degrees)
  cr.close_path()

# draw a togglable button
def draw_button(cr, area, label, color, toggled):
  radius = 3
  cr.set_source_rgba(color.red, color.green, color.blue, 0.1)
  draw_round_rect(cr, area.x, area.y, area.width, area.height, radius)
  cr.fill()
  if (toggled):
    cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
    cr.set_line_width(2)
    draw_round_rect(cr, area.x, area.y, area.width, area.height, radius)
    cr.stroke()
  if (len(label) > 0):
    if (toggled):
      cr.set_source_rgba(color.red, color.green, color.blue, 1.0)
    else:
      cr.set_source_rgba(color.red, color.green, color.blue, 0.5)
    cr.set_font_size(round(min(area.width, area.height) / 2))
    (bx, by, tw, th, nx, ny) = cr.text_extents(label)
    cr.move_to(area.x + (area.width / 2) - (tw / 2) - bx, 
               area.y + (area.height / 2) - (th / 2) - by)
    cr.show_text(label)
    
# draw a connection between two endpoints
def draw_connection(cr, lp, rp, style):
  draw_path(cr, (lp, rp), style)
  
# draw a series of connected nodes
def draw_path(cr, points, style):
  i = 0
  was_node = False
  for s in style:
    while ((points[i] is None) and (i < len(points) - 1)):
      i += 1
    if (s in '"-~\\/01'):
      draw_line(cr, points[i], points[i+1], s)
      i += 1
      was_node = False
    elif (s in '.o*x<>([{}])'):
      if (was_node):
        i += 1
      draw_node(cr, points[i], s)
      was_node = True

# draw a node corresponding to the given style character
def draw_node(cr, p, style):
  if (style == 'o'):
    draw_open_node(cr, p.x, p.y, RADIUS)
  elif (style == '*'):
    draw_closed_node(cr, p.x, p.y, RADIUS)
  elif (style == '.'):
    draw_closed_node(cr, p.x, p.y, RADIUS / 2)
  elif (style == 'x'):
    draw_unplug_node(cr, p.x, p.y, RADIUS)
  elif (style in '<>'):
    draw_arrow(cr, p.x, p.y, RADIUS, style)
  elif (style in '([{}])'):
    draw_bracket(cr, p.x, p.y, BRACKET_WIDTH, BRACKET_HEIGHT, style)

# draw a connection corresponding to the given style character
def draw_line(cr, p1, p2, style):
  if ((p1 is None) or (p2 is None)): return
  if (p1.x > p2.x):
    lp = p2
    rp = p1
  else:
    lp = p1
    rp = p2
  if (style == '0'):
    draw_switch(cr, lp, rp, False)
    return
  elif (style == '1'):
    draw_switch(cr, lp, rp, True)
    return
  cr.save()
  if (style == '"'):
    cr.set_dash((3, 2))
  cr.set_line_width(2)
  cr.move_to(lp.x, lp.y)
  if (style in '\\/'):
    cr.translate(lp.x, lp.y)
    if (style == '/'):
      cr.rotate(- (math.pi / 6))
    else:
      cr.rotate(math.pi / 6)
    cr.line_to(rp.x - lp.x, rp.y - lp.y)
  elif ((lp.x == rp.x) or (lp.y == rp.y) or (style == '-')):
    cr.line_to(rp.x, rp.y)
  elif (style == '~'):
    cx = abs((rp.x - lp.x) / 2)
    cr.curve_to(lp.x + cx, lp.y, rp.x - cx, rp.y, rp.x, rp.y)
  cr.stroke()
  cr.restore()

# draw a circle indicating an open connection port
def draw_open_node(cr, x, y, radius):
  r = radius - 1
  cr.move_to(x + r, y)  
  # clear the center in case there are connections drawn to it;
  #  we just invert the current color so a transparent window isn't needed
  cr.save()
  (red, green, blue, a) = cr.get_source().get_rgba() 
  cr.set_source_rgba(1 - red, 1 - green, 1 - blue, 1)
  cr.arc(x, y, r, 0, math.pi * 2)
  cr.fill()
  cr.restore()
  # draw the outline
  cr.set_line_width(2)
  cr.arc(x, y, r, 0, math.pi * 2)
  cr.stroke()
# draw a circle indication a connected endpoint
def draw_closed_node(cr, x, y, radius):
  cr.move_to(x + radius, y)
  cr.arc(x, y, radius, 0, math.pi * 2)
  cr.fill()
# draw an X indicating a connection can be unplugged
def draw_unplug_node(cr, x, y, radius):
  cr.set_line_width(2)
  r = radius
  cr.move_to(x - r, y - r)
  cr.line_to(x + r, y + r)
  cr.move_to(x - r, y + r)
  cr.line_to(x + r, y - r)
  cr.stroke()
# draw an arrow indicating the endpoint of a possible connection
def draw_arrow(cr, x, y, radius, s):
  if (s == '<'):
    s = -1
  else:
    s = 1
  cr.move_to(x, y - radius)
  cr.line_to(x + (radius * 2 * s), y)
  cr.line_to(x, y + radius)
  cr.close_path()
  cr.fill()
# draw a bracket indicating the beginning or end of a path
def draw_bracket(cr, x, y, width, height, s):
  if (s in '}])'):
    s = -1
  else:
    s = 1
  cr.move_to(x + (width * s), y - height)
  cr.curve_to(x, y - height, x + (width * s), y, x, y)
  cr.curve_to(x + (width * s), y, x, y + height, x + (width * s), y + height)
  cr.stroke()
  
# draw a switch that can be opened and closed
def draw_switch(cr, p1, p2, closed=False):
  outer = math.sqrt(math.pow(p2.x - p1.x, 2) + 
                    math.pow(p2.y - p1.y, 2))
  inner = min(outer - (RADIUS * 4), RADIUS * 6)
  f1 = (inner / outer) / 2.0
  f2 = 1.0 - f1 
  ip1 = geom.Point(p1.x + ((p2.x - p1.x) * f1),
                   p1.y + ((p2.y - p1.y) * f1))
  ip2 = geom.Point(p1.x + ((p2.x - p1.x) * f2),
                   p1.y + ((p2.y - p1.y) * f2))
  if (closed):
    s = '-'
  else:
    s = '/'
  draw_path(cr, (p1, ip1, ip2, p2), '-.'+s+'.-')
  
# draw a note
def draw_note(cr, note, area):
  x = area.x
  y = area.y
  w = area.width
  h = area.height
  # get the velocity for scaling the note
  velocity = 1
  try:
    if (note.velocity != None):
      velocity = note.velocity
  except AttributeError: pass
  # size the note based on velocity
  vh = 2 + ((h - 4) * velocity)
  inset = math.floor((h - vh) / 2.0)
  y += inset
  h -= (inset * 2)
  # never allow a note to be narrower than it is tall
  w = max(w, h)
  # make sure the radius is no more than half the size
  r = min(3, h / 2.0)
  # draw the note as a box
  draw_round_rect(cr, x, y, w, h, r)
  cr.fill()

# draw the repeat sign
def draw_repeat(cr, area):
  cr.set_line_width(2)
  x = area.x + area.width
  cr.move_to(x, 0)
  cr.line_to(x, area.height)
  cr.stroke()
  cr.set_line_width(1)
  x -= 3.5
  cr.move_to(x, 0)
  cr.line_to(x, area.height)
  cr.stroke()
  x -= 4.5
  y = round(area.height / 2)
  cr.arc(x, y - 5, 1.5, 0, 2 * math.pi)
  cr.arc(x, y + 5, 1.5, 0, 2 * math.pi)
  cr.fill()
# draw the caps at the start and end of a block
def draw_cap(cr, area, direction):
  inner = (area.width - 2) * direction
  outer = (area.width * direction)
  if (direction > 0):
    cr.move_to(area.x, 0)
  else:
    cr.move_to(area.x + area.width, 0)
  cr.rel_line_to(outer, 0)
  cr.rel_line_to(0, 1)
  cr.rel_line_to(- inner, 1)
  cr.rel_line_to(0, area.height - 4)
  cr.rel_line_to(inner, 1)
  cr.rel_line_to(0, 1)
  cr.rel_line_to(- outer, 0)
  cr.close_path()
  cr.fill()
