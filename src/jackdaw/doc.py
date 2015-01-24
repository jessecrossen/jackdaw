# coding=utf-8

import yaml
try:
  import cPickle as pickle
except:
  import pickle

import observable
import serializable
from model import Model, ModelList
from track import TrackList, SequencerUnit
from transport import Transport
from midi import DeviceAdapterList, DeviceListUnit
from audio import SystemPlaybackUnit
from unit import UnitList, PatchBay
from undo import UndoManager

# make a units-to-pixels mapping with observable changes
class ViewScale(observable.Object):
  def __init__(self, pixels_per_second=24.0, pitch_height=16.0, 
                     controller_height=24.0, time_offset=0.0):
    observable.Object.__init__(self)
    self._pixels_per_second = pixels_per_second
    self._time_offset = time_offset
    self._pitch_height = pitch_height
    self._controller_height = controller_height
  def serialize(self):
    return({
      'pixels_per_second': self.pixels_per_second,
      'time_offset': self.time_offset,
      'pitch_height': self.pitch_height
    })
  @property
  def pixels_per_second(self):
    return(self._pixels_per_second)
  @pixels_per_second.setter
  def pixels_per_second(self, value):
    if (value != self._pixels_per_second):
      self._pixels_per_second = float(value)
      self.on_change()
  @property
  def pitch_height(self):
    return(self._pitch_height)
  @pitch_height.setter
  def pitch_height(self, value):
    if (value != self._pitch_height):
      self._pitch_height = float(value)
      self.on_change()
  @property
  def controller_height(self):
    return(self._controller_height)
  @controller_height.setter
  def controller_height(self, value):
    if (value != self._controller_height):
      self._controller_height = float(value)
      self.on_change()
  @property
  def time_offset(self):
    return(self._time_offset)
  @time_offset.setter
  def time_offset(self, value):
    if (value != self._time_offset):
      self._time_offset = value
      self.on_change()
  # get the x offset of the current time
  @property
  def x_offset(self):
    return(self.x_of_time(self.time_offset))
  # convenience functions
  def time_of_x(self, x):
    return(float(x) / self._pixels_per_second)
  def x_of_time(self, time):
    return(float(time) * self._pixels_per_second)
  def height_of_track(self, track):
    min_height = 4 * self.pitch_height
    pitches_height = len(track.pitches) * self.pitch_height
    controllers_height = len(track.controllers) * self.controller_height
    return(max(min_height, pitches_height + controllers_height))
  @property
  def track_spacing(self):
    return(6.0)
serializable.add(ViewScale)

# represent a document, which collects the elements of a persistent workspace
class Document(Model):
  def __init__(self, tracks=None, devices=None, transport=None,
                     view_scale=None, units=None, patch_bay=None):
    Model.__init__(self)
    # the file path to save to
    self.path = None
    # transport
    if (transport is None):
      transport = Transport()
    self.transport = transport
    # time scale
    if (view_scale is None):
      view_scale = ViewScale()
    self.view_scale = view_scale
    # devices
    if (devices is None):
      devices = DeviceAdapterList()
    self.devices = devices
    # a list of units on the workspace
    if (units is None):
      units = UnitList()
    self.units = units
    self.units.add_observer(self.on_change)
    self.units.add_observer(self.update_transport_duration)
    self.update_transport_duration()
    # a list of connections between units
    if (patch_bay is None):
      patch_bay = PatchBay()
    self.patch_bay = patch_bay
    self.patch_bay.add_observer(self.on_change)
  def serialize(self):
    return({
      'devices': self.devices,
      'transport': self.transport,
      'view_scale': self.view_scale,
      'units': self.units,
      'patch_bay': self.patch_bay
    })
  @property
  def model_refs(self):
    return((self.transport, self.view_scale, self.devices, 
            self.units, self.patch_bay))
  # remove a unit from the document
  def remove_unit(self, unit, inputs=(), outputs=()):
    units = self.units
    patch_bay = self.patch_bay
    UndoManager.begin_action((units, patch_bay, inputs, outputs))
    patch_bay.remove_connections_for_unit(unit)
    for item in inputs:
      patch_bay.remove_connections_for_unit(item)
    for item in outputs:
      patch_bay.remove_connections_for_unit(item)
    units.remove(unit)
    # remove the unit from any groups it might be a part of
    for group in units:
      if ((hasattr(group, 'units')) and (unit in group.units)):
        group.units.remove(unit)
    UndoManager.end_action()
  # update the duration of the transport based on the length of the tracks
  def update_transport_duration(self):
    duration = 0.0
    for unit in self.units:
      if (hasattr(unit, 'tracks')):
        for track in unit.tracks:
          duration = max(duration, track.duration)
    self.transport.duration = duration
  # save the document to a file
  def save(self):
    output_stream = open(self.path, 'w')
    if (self.path.endswith('.yml')):
      output_stream.write(yaml.dump(self))
    else:
      output_stream.write(pickle.dumps(self, protocol=2))
    output_stream.close()
  # load a document from a file
  @classmethod
  def get_from_path(self, path):
    if (len(path) == 0): return(None)
    input_stream = open(path, 'r')
    if (not input_stream): return(None)
    s = input_stream.read()
    input_stream.close()
    document = None
    if (path.endswith('.yml')):
      document = yaml.load(s)
    if (document is None):
      document = pickle.loads(s)
    if (document is not None):
      document.path = path
    return(document)
serializable.add(Document)
