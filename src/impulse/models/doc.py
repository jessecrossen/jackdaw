# coding=utf-8

import sys
import copy

from ..common import observable
  
# make a base class to implement common functions of the model layer
class Model(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    # initialize cached data attributes  
    self.invalidate()
  # invalidate cached data when the model changes
  def on_change(self):
    self.invalidate()
    observable.Observable.on_change(self)
  # override to invalidate cached data
  def invalidate(self):
    pass

# make a base class to implement common functions for lists of Model instances
class ModelList(observable.List):
  def __init__ (self, value=()):
    observable.List.__init__(self, value)
    # initialize cached data attributes  
    self.invalidate()
  # invalidate cached data when the model changes
  def on_change(self):
    self.invalidate()
    observable.Observable.on_change(self)
  # override to invalidate cached data
  def invalidate(self):
    pass

# represents a single note event with time, pitch, velocity, and duration
#  - time and duration are in seconds
#  - pitch is a MIDI note number, 
#  - velocity is a fraction between 0 and 1
class Note(Model):
  def __init__(self, time=None, pitch=None, velocity=1, duration=0):
    Model.__init__(self)
    self._time = time
    self._duration = duration
    self._pitch = pitch
    self._velocity = velocity
  
  # the time relative to the beginning of its container when the note 
  #  begins playing (in seconds)
  @property
  def time(self):
    return(self._time)
  @time.setter
  def time(self, value):
    if (self._time != value):
      self._time = value
      self.on_change()
  # the length of time the note plays (in seconds)
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (self._duration != value):
      self._duration = value
      self.on_change()
  # a MIDI note number from 0-127 identifying the note's pitch
  @property
  def pitch(self):
    return(self._pitch)
  @pitch.setter
  def pitch(self, value):
    if (self._pitch != value):
      self._pitch = value
      self.on_change()
  # a floating point number from 0-1 identifying how hard the note is played
  @property
  def velocity(self):
    return(self._velocity)
  @velocity.setter
  def velocity(self, value):
    if (self._velocity != value):
      self._velocity = value
      self.on_change()
  # define a copy operation for notes
  def __copy__(self):
    return(Note(time=self.time, 
                pitch=self.pitch,
                velocity=self.velocity,
                duration=self.duration))

# represents a series of events grouped into a logical block with a duration
class EventList(ModelList):
  def __init__(self, events=(), duration=60, divisions=1):
    ModelList.__init__(self, events)
    self._duration = duration
    self._divisions = divisions
  
  # the total length of time the events occur in (in seconds)
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (self._duration != value):
      self._duration = value
      self.on_change()
  # the number of segments to divide the duration into
  # set this to 0 to indicate the time is undivided
  @property
  def divisions(self):
    return(self._divisions)
  @divisions.setter
  def divisions(self, value):
    if (self._divisions != value):
      self._divisions = value
      self.on_change()
  
  # invalidate cached data
  def invalidate(self):
    self._pitches = None
    self._times = None
  
  # lazily get a list of unique pitches for all notes in the list
  @property
  def pitches(self):
    if (self._pitches == None):
      pitches = set()
      for event in self:
        if (hasattr(event, 'pitch')):
          pitches.add(event.pitch)
      self._pitches = list(pitches)
      self._pitches.sort()
    return(self._pitches)
  # lazily get a list of unique times for all notes in the list
  @property
  def times(self):
    if (self._times == None):
      times = set()
      for event in self:
        if (hasattr(event, 'time')):
          times.add(event.time)
      self._times = list(times)
      self._times.sort()
    return(self._times)

# represents a placement of an event list on a timeline with its own duration
# the event list is truncated or repeated to fill the duration
class Block(Model):
  def __init__(self, events, time=0, duration=0):
    Model.__init__(self)
    self._events = events
    self._events.add_observer(self.on_change)
    self._time = time
    self._duration = duration
  
  # the events in the block
  @property
  def events(self):
    return(self._events)
  @events.setter
  def events(self, value):
    self._events.remove_observer(self.on_change)
    self._events = value
    self._events.add_observer(self.on_change)
    self.on_change()
  # the time relative to the beginning of its container when the block 
  #  begins playing (in seconds)
  @property
  def time(self):
    return(self._time)
  @time.setter
  def time(self, value):
    if (self._time != value):
      self._time = value
      self.on_change()
  # the total length of time the block plays (in seconds)
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (self._duration != value):
      self._duration = value
      self.on_change()
  
  # invalidate cached data
  def invalidate(self):
    self._pitches = None
    self._times = None
  
  # get all event times within the block
  @property
  def times(self):
    if (self._times == None):
      times = set()
      repeat_time = self.events.duration
      for time in self.events.times:
        times.add(time)
        if (repeat_time > 0):
          time += repeat_time
          while (time < self.duration):
            times.add(time)
            time += repeat_time
      time = 0.0
      while ((time < self.duration) and (repeat_time > 0)):
        times.add(time)
        time += repeat_time
      self._times = list(times)
      self._times.sort()
    return(self._times)
  # get all pitch classes within the block
  @property
  def pitches(self):
    return(self.events.pitches)
  
  # join repeats into one event list
  def join_repeats(self):
    repeat_time = self.events.duration
    if (repeat_time >= self.duration): return
    new_events = EventList(duration=self.duration)
    time = 0
    while ((time < self.duration) and (repeat_time > 0)):
      for event in self.events:
        if (time + event.time < self.duration):
          new_event = copy.copy(event)
          new_event.time += time
          new_events.append(new_event)
      time += repeat_time
    self.events = new_events
  
  # join multiple blocks into this block
  def join(self, blocks, tracks=None):
    # make sure the list of blocks includes this one
    blocks = set(blocks)
    blocks.add(self)
    # get the timespan of the blocks
    mintime = self.time
    maxtime = self.time + self.events.duration
    for block in blocks:
      mintime = min(block.time, mintime)
      maxtime = max(block.time + block.events.duration, maxtime)
      # join repeated sections in the source blocks
      block.join_repeats()
    # make a new event list for the joined events
    new_events = EventList(duration=(maxtime - mintime))
    # copy events into the joined list
    for block in blocks:
      for event in block.events:
        event_copy = copy.copy(event)
        event_copy.time += (block.time - mintime)
        new_events.append(event_copy)
    # sort events by time
    new_events.sort(key=lambda e: e.time)
    # update the extents of this block
    self._time = mintime
    self._duration = (maxtime - mintime)
    # swap in the new event list for this block
    self.events = new_events
    # remove all other blocks if possible
    blocks.remove(self)
    if (tracks is not None):
      for track in tracks:
        track_blocks = list(track)
        for block in track_blocks:
          if (block in blocks):
            track.remove(block)
  
  # break apart repeats of the block's events into new blocks
  def split_repeats(self, track):
    repeat_time = self.events.duration
    if (repeat_time >= self.duration): return
    time = repeat_time
    while ((time < self.duration) and (repeat_time > 0)):
      event_list = EventList(duration=repeat_time)
      for event in self.events:
        new_event = copy.copy(event)
        event_list.append(new_event)
      start_time = self.time + time
      end_time = min(start_time + repeat_time, self.time + self.duration)
      block = Block(event_list, 
                    time=start_time,
                    duration=(end_time - start_time))
      track.append(block)
      time += repeat_time
    self.duration = repeat_time
  
  # split the block on the given time boundaries
  def split(self, times, track):
    event_lists = [ ]
    times = list(times)
    times.sort()
    if (times[0] != 0.0):
      times.insert(0, 0.0)
    if (times[-1] != self.duration):
      times.append(self.duration)
    # move existing events into time ranges
    unsorted_events = set(self.events)
    for i in range(1, len(times)):
      still_unsorted_events = set()
      start_time = times[i - 1]
      end_time = times[i]
      event_list = EventList(duration=(end_time - start_time))
      for event in unsorted_events:
        if (event.time < end_time):
          new_event = copy.copy(event)
          new_event.time -= start_time
          event_list.append(new_event)
        else:
          still_unsorted_events.add(event)
      event_lists.append(event_list)
      unsorted_events = still_unsorted_events
    # make this block contain the first set of events
    self._duration = event_lists[0].duration
    self.events = event_lists[0]
    for i in range(1, len(event_lists)):
      block = Block(event_lists[i], 
        time=self.time + times[i],
        duration=event_lists[i].duration)
      track.append(block)
  
# represent a track, which can contain multiple blocks
class Track(ModelList):

  # names of the cyclical pitch classes starting at MIDI note 0
  PITCH_CLASS_NAMES = ( 
    'C', 'D♭', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B' )

  def __init__(self, blocks=(), duration=60):
    ModelList.__init__(self, blocks)
    self._duration = duration
    self._solo = False
    self._mute = False
    self._arm = False
    self._level = 1.0
    self._pan = 0.0
    self._pitch_names = dict()
    
  # invalidate cached data
  def invalidate(self):
    self._pitches = None
    self._times = None
    # whether the track is enabled for playback 
    # (this will be controlled by the track list)
    self.enabled = True
  
  # get and set user-defined names for pitches
  @property
  def pitch_names(self):
    return(self._pitch_names)
  @pitch_names.setter
  def pitch_names(self, value):
    self._pitch_names = value
    self.on_change()
  
  # get a name for a MIDI note number
  def name_of_pitch(self, pitch):
    # snap to the closest whole number
    pitch = int(round(pitch))
    # see if there's a user-defined mapping for it
    if (pitch in self._pitch_names):
      return(self._pitch_names[pitch])
    # otherwise look it up in the list of pitch classes
    return(self.PITCH_CLASS_NAMES[pitch % 12])
    
  # the total length of time of the track content (in seconds)
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (self._duration != value):
      self._duration = value
      self.on_change()
  
  # whether the track should play by itself or as part of a solo group
  @property
  def solo(self):
    return(self._solo)
  @solo.setter
  def solo(self, value):
    value = (value == True)
    if (self._solo != value):
      self._solo = value
      self.on_change()
  # whether the track should be excluded from playback
  @property
  def mute(self):
    return(self._mute)
  @mute.setter
  def mute(self, value):
    value = (value == True)
    if (self._mute != value):
      self._mute = value
      self.on_change()
  # whether the track is armed for recording
  @property
  def arm(self):
    return(self._arm)
  @arm.setter
  def arm(self, value):
    value = (value == True)
    if (self._arm != value):
      self._arm = value
      self.on_change()
  # the mix level of the track from 0.0 (silent) to 1.0 (loudest)
  @property
  def level(self):
    return(self._level)
  @level.setter
  def level(self, value):
    value = min(max(0.0, value), 1.0)
    if (self._level != value):
      self._level = value
      self.on_change()
  # the stereo pan of the track from -1.0 (hard left) 
  #  to 0.0 (center) to 1.0 (hard right)
  @property
  def pan(self):
    return(self._pan)
  @pan.setter
  def pan(self, value):
    value = min(max(-1.0, value), 1.0)
    if (self._pan != value):
      self._pan = value
      self.on_change()
  
  # get a list of unique times for all the notes in the track
  @property
  def times(self):
    if (self._times == None):
      times = set()
      for block in self:
        # add the block boundaries
        times.add(block.time)
        times.add(block.time + block.duration)
        # add the times of all events in the block
        for time in block.times:
          times.add(block.time + time)
      self._times = list(times)
      self._times.sort()
    return(self._times)
  # get a list of unique pitches for all the notes in the track
  @property
  def pitches(self):
    if (self._pitches == None):
      pitches = set()
      for block in self:
        for pitch in block.pitches:
          pitches.add(pitch)
      self._pitches = list(pitches)
      self._pitches.sort()
    return(self._pitches)

# represent a list of tracks
class TrackList(ModelList):
  def __init__(self, tracks=()):
    ModelList.__init__(self, tracks)
  
  def on_change(self):
    # transfer global track state to the tracks
    solos = set()
    for track in self:
      if (track.solo):
        solos.add(track)
    if (len(solos) > 0):
      for track in self:
        track.enabled = (track in solos)
    else:
      for track in self:
        track.enabled = not track.mute
    ModelList.on_change(self)
  
  # invalidate cached data
  def invalidate(self):
    self._max_duration = None
    self._times = None
    
  # return the duration of the longest track in the list
  @property
  def duration(self):
    if (self._max_duration is None):
      self._max_duration = 0
      for track in self:
        self._max_duration = max(self._max_duration, track.duration)
    return(self._max_duration)
  # get a list of unique times for all tracks in the list
  @property
  def times(self):
    if (self._times == None):
      times = set()
      for track in self:
        for time in track.times:
          times.add(time)
      self._times = list(times)
      self._times.sort()
    return(self._times)
    
# represent a directed patch bay that routes between two lists
class PatchBay(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self._connections = set()
    self._update_maps()
  @property
  def connections(self):
    return(set(self._connections))
  @connections.setter
  def connections(self, value):
    removed = self.connections
    added = set()
    for c in value:
      if c in self._connections:
        removed.remove(c)
      else:
        added.add(c)
    for (from_what, to_what) in removed:
      self.disconnect(from_what, to_what)
    for (from_what, to_what) in added:
      self.connect(from_what, to_what)
  # make a connection between two objects
  def connect(self, from_what, to_what):
    connection = (from_what, to_what)
    if (connection not in self._connections):
      self._connections.add((from_what, to_what))
      self._update_maps()
      self.on_change()
  # break a connection between two objects
  def disconnect(self, from_what, to_what):
    connection = (from_what, to_what)
    if (connection in self._connections):
      self._connections.remove(connection)
      self._update_maps()
      self.on_change()
  # get the items that are connected on either side
  @property
  def from_items(self):
    return(self._from_items.keys())
  @property
  def to_items(self):
    return(self._to_items.keys())
  # get the items something is connected to/from
  def items_connected_from(self, from_what):
    try:
      return(set(self._from_items[from_what]))
    except KeyError:
      return(())
  def items_connected_to(self, to_what):
    try:
      return(set(self._to_items[to_what]))
    except KeyError:
      return(())
  # update the maps from items to what they're connected to
  def _update_maps(self):
    self._from_items = dict()
    self._to_items = dict()
    for (from_what, to_what) in self._connections:
      if (from_what not in self._from_items):
        self._from_items[from_what] = set()
      self._from_items[from_what].add(to_what)
      if (to_what not in self._to_items):
        self._to_items[to_what] = set()
      self._to_items[to_what].add(from_what)

# represent a document, which can contain multiple tracks
class Document(Model):
  def __init__(self):
    Model.__init__(self)
    self.tracks = TrackList()
    self.tracks.add_observer(self.on_change)
    self.input_patch_bay = PatchBay()
    self.input_patch_bay.add_observer(self.on_input_change)
    self.output_patch_bay = PatchBay()
    self.output_patch_bay.add_observer(self.on_output_change)
  
  # connect input devices when they're routed to something in the patch bay
  def on_input_change(self):
    for device in self.input_patch_bay.from_items:
      if (not device.is_connected):
        device.connect()
  # connect output devices when there's something routed to them
  def on_output_change(self):
    for device in self.output_patch_bay.to_items:
      if (not device.is_connected):
        device.connect()

