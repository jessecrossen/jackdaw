import jackpatch

import serializable
from model import Model, ModelList

from PySide.QtCore import *

# represent a unit, which can be connected to other units
class Unit(Model):
  name_changed = Signal()
  def __init__(self, name='Unit', x=0, y=0, width=0, height=0, hue=None):
    Model.__init__(self)
    self._name = name
    self._x = x
    self._y = y
    self._width = width
    self._height = height
    self._hue = hue
  # get and set the name of the unit
  @property
  def name(self):
    return(self._name)
  @name.setter
  def name(self, value):
    if (value != self._name):
      self._name = value
      self.on_change()
      self.name_changed.emit()
  # the hue to draw the unit in (0.0 - 1.0 or None for no color)
  @property
  def hue(self):
    return(self._hue)
  @hue.setter
  def hue(self, value):
    if (self._hue != value):
      self._hue = value
      self.on_change()
  # get and set the position of the unit on the workspace
  @property
  def x(self):
    return(self._x)
  @x.setter
  def x(self, value):
    if (value != self._x):
      self._x = value
      self.on_change()
  @property
  def y(self):
    return(self._y)
  @y.setter
  def y(self, value):
    if (value != self._y):
      self._y = value
      self.on_change()
  # get and set the preferred size of the unit on the workspace 
  #  (which will not be respected by all unit types)
  @property
  def width(self):
    return(self._width)
  @width.setter
  def width(self, value):
    if (value != self._width):
      self._width = value
      self.on_change()
  @property
  def height(self):
    return(self._height)
  @height.setter
  def height(self, value):
    if (value != self._height):
      self._height = value
      self.on_change()
  # make a position and size interfaces for easy compatibility 
  #  with QGraphicsItem
  def pos(self):
    return(QPointF(self.x, self.y))
  def setPos(self, pos):
    self.x = pos.x()
    self.y = pos.y()
  def boundingRect(self):
    w = self.width
    h = self.height
    return(QRectF(- (w / 2), - (h / 2), w, h))
  def rect(self):
    w = self.width
    h = self.height
    return(QRectF(self.x - (w / 2), self.y - (h / 2), w, h))
  def setRect(self, rect):
    self.width = rect.width()
    self.height = rect.height()
    self.x = rect.x() + (rect.width() / 2)
    self.y = rect.y() + (rect.height() / 2)
  # unit serialization
  def serialize(self):
    obj = { 
      'name': self.name,
      'x': self.x,
      'y': self.y
    }
    if (self.width > 0):
      obj['width'] = self.width
    if (self.height > 0):
      obj['height'] = self.height
    if (self.hue is not None):
      obj['hue'] = self.hue
    return(obj)
serializable.add(Unit)

# represent a list of units
class UnitList(ModelList):
  def __init__(self, units=()):
    ModelList.__init__(self, units)
  # track serialization
  def serialize(self):
    return({ 
      'units': list(self)
    })
serializable.add(UnitList)

# make a mixin to make a model a signal source
class Source(object):
  def __init__(self):
    self._source_type = 'mono'
    self._source_port = None
    # keep track of the number of connections to the port for bookkeeping
    self.source_connections = 0
  # return the type of signal emitted by this source
  @property
  def source_type(self):
    return(self._source_type)
  # get/set the JACK port or tuple of ports that send data
  @property
  def source_port(self):
    return(self._source_port)
  @source_port.setter
  def source_port(self, port):
    if (port is not self._source_port):
      self._source_port = port
      try:
        self.on_change()
      except AttributeError: pass

# make a mixin to make a model a signal sink
class Sink(object):
  def __init__(self):
    self._sink_type = 'mono'
    self._sink_port = None
    # keep track of the number of connections to the port for bookkeeping
    self.sink_connections = 0
  # return the type of signal emitted by this source
  @property
  def sink_type(self):
    return(self._sink_type)
  # get/set the JACK port or tuple of ports that accept data
  @property
  def sink_port(self):
    return(self._sink_port)
  @sink_port.setter
  def sink_port(self, port):
    if (port is not self._sink_port):
      self._sink_port = port
      try:
        self.on_change()
      except AttributeError: pass

# represent a connection between a source and sink
class Connection(Model):
  # keep a central JACK client for managing connections between ports
  jack_client = None
  def __init__(self, source=None, sink=None):
    Model.__init__(self)
    self._source = None
    self._sink = None
    self._connected_source_port = None
    self._connected_sink_port = None
    self.source = source
    self.sink = sink
  @property
  def model_refs(self):
    refs = [ ]
    if (isinstance(self.source, Model)):
      refs.append(self.source)
    if (isinstance(self.sink, Model)):
      refs.append(self.sink)
    return(refs)
  @property
  def source(self):
    return(self._source)
  @source.setter
  def source(self, value):
    old_source = None
    if (value is not self._source):
      if (self._source is not None):
        old_source = self._source
        old_source.source_connections -= 1
        try:
          self._source.remove_observer(self.on_change)
        except AttributeError: pass
      self._source = value
      if (self._source is not None):
        self._source.source_connections += 1
        try:
          self._source.add_observer(self.on_change)
        except AttributeError: pass
      self.on_change()
      # update the old source after a delay, to allow 
      #  disconnection requests to propagate through JACK
      try:
        QTimer.singleShot(10, old_source.on_change)
      except AttributeError: pass
  @property
  def sink(self):
    return(self._sink)
  @sink.setter
  def sink(self, value):
    old_sink = None
    if (value is not self._sink):
      if (self._sink is not None):
        old_sink = self._sink
        old_sink.sink_connections -= 1
        try:
          self._sink.remove_observer(self.on_change)
        except AttributeError: pass
      self._sink = value
      if (self._sink is not None):
        self._sink.sink_connections += 1
        try:
          self._sink.add_observer(self.on_change)
        except AttributeError: pass
      self.on_change()
      # update the old source after a delay, to allow 
      #  disconnection requests to propagate through JACK
      try:
        QTimer.singleShot(10, old_sink.on_change)
      except AttributeError: pass
      
  # lazy-load a jack client to make patchbay connections
  def get_jack_client(self):
    if (Connection.jack_client is None):
      Connection.jack_client = jackpatch.Client('jackdaw-patchbay')
    return(Connection.jack_client)
  # propagate port and connection changes to JACK
  def on_change(self):
    source_port = self._source.source_port if (self._source is not None) else None
    sink_port = self._sink.sink_port if (self._sink is not None) else None
    routed = False
    if ((self._connected_source_port is not source_port) and 
        (self._connected_sink_port is not sink_port)):
      if ((self._connected_source_port is not None) and 
          (self._connected_sink_port is not None)):
        self.route(self._connected_source_port, 
                   self._connected_sink_port,
                   connected=False)
        routed = True
      if ((source_port is not None) and 
          (sink_port is not None)):
        self.route(source_port, sink_port, connected=True)
        routed = True
      self._connected_source_port = source_port
      self._connected_sink_port = sink_port
    # notify the source and sink that they changed connections
    if (routed):
      self._on_route_changed()
    # do normal change actions
    Model.on_change(self)
  # connect or disconnect a source and sink (either ports or port tuples)
  def route(self, source, sink, connected=True):
    client = self.get_jack_client()
    # cast both ends to be tuples
    if (isinstance(source, jackpatch.Port)):
      source = (source,)
    if (isinstance(sink, jackpatch.Port)):
      sink = (sink,)
    source_ports = len(source)
    sink_ports = len(sink)
    for i in range(0, max(source_ports, sink_ports)):
      source_port = source[min(i, source_ports - 1)]
      sink_port = sink[min(i, sink_ports - 1)]
      if (connected):
        client.connect(source_port, sink_port)
      else:
        client.disconnect(source_port, sink_port)
  # disconnect when deleted
  def __del__(self):
    if (self._source is not None):
      self._source.source_connections -= 1
    if (self._sink is not None):
      self._sink.sink_connections -= 1
    if ((self._connected_source_port is not None) and 
          (self._connected_sink_port is not None)):
      self.route(self._connected_source_port, 
                 self._connected_sink_port,
                 connected=False)
      self._on_route_changed()
  # notify the endpoints when something changes, after a delay to allow 
  #  disconnection requests to propagate through JACK
  def _on_source_changed(self):
    try:
      QTimer.singleShot(10, self._source.on_change)
    except AttributeError: pass
  def _on_sink_changed(self):
    try:
      QTimer.singleShot(10, self._sink.on_change)
    except AttributeError: pass
  def _on_route_changed(self):
    self._on_source_changed()
    self._on_sink_changed()
  # connection serialization
  def serialize(self):
    return({ 
      'source': self.source,
      'sink': self.sink
    })
serializable.add(Connection)

# represent a patch bay that maintains connections between units
class PatchBay(ModelList):
  def __init__(self, connections=()):
    ModelList.__init__(self, connections)
  def invalidate(self):
    self._source_map = None
    self._sink_map = None
  # make a mapping that indexes sources by sink
  def _make_source_map(self):
    if (self._source_map is None):
      self._source_map = dict()
      for c in self:
        if (c.sink not in self._source_map):
          self._source_map[c.sink] = list()
        self._source_map[c.sink].append(c.source)
    return(self._source_map)
  # make a mapping that indexes sinks by source
  def _make_sink_map(self):
    if (self._sink_map is None):
      self._sink_map = dict()
      for c in self:
        if (c.source not in self._sink_map):
          self._sink_map[c.source] = list()
        self._sink_map[c.source].append(c.sink)
    return(self._sink_map)
  # get a list of all sinks connected to the given source
  def sources_for_sink(self, sink):
    m = self._make_source_map()
    if (sink in m):
      return(m[sink])
    return(())
  # get a list of all sources connected to the given sink
  def sinks_for_source(self, source):
    m = self._make_sink_map()
    if (source in m):
      return(m[source])
    return(())
  # remove connections for the given source/sink
  def remove_connections_for_unit(self, unit):
    remove_connections = set()
    for c in self:
      if ((c.source is unit) or (c.sink is unit)):
        remove_connections.add(c)
    for c in remove_connections:
      c.source = None
      c.sink = None
      self.remove(c)
  def serialize(self):
    return({
      'connections': list(self)
    })
serializable.add(PatchBay)

