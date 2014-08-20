# coding=utf-8

import time
import yaml
import copy

from gi.repository import GLib

from ..common import observable, serializable

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
  def __repr__(self):
    return('Note(time=%0.9g, pitch=%d, velocity=%g, duration=%0.9g)' %
            (self.time, self.pitch, self.velocity, self.duration))
  def serialize(self):
    return({ 
      'time': self.time,
      'pitch': self.pitch,
      'velocity': self.velocity,
      'duration': self.duration
    })
serializable.add(Note)

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
  # serialization
  def serialize(self):
    return({ 
      'events': list(self),
      'duration': self.duration,
    'divisions': self.divisions
    })
serializable.add(EventList)

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
  # block serialization
  def serialize(self):
    return({
      'events': self.events,
      'duration': self.duration,
      'time': self.time
    })
serializable.add(Block)

# represent a track, which can contain multiple blocks
class Track(ModelList):

  # names of the cyclical pitch classes starting at MIDI note 0
  PITCH_CLASS_NAMES = ( 
    'C', 'D♭', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B' )

  def __init__(self, blocks=(), duration=60, 
                     solo=False, mute=False, arm=False,
                     level=1.0, pan=0.0, pitch_names=None):
    ModelList.__init__(self, blocks)
    self._duration = duration
    self._solo = solo
    self._mute = mute
    self._arm = arm
    self._level = level
    self._pan = pan
    if (pitch_names is None): 
      pitch_names = dict()
    self._pitch_names = pitch_names
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
  # track serialization
  def serialize(self):
    return({ 
      'blocks': list(self),
      'duration': self.duration,
      'solo': self.solo,
      'mute': self.mute,
      'arm': self.arm,
      'level': self.level,
      'pan': self.pan,
      'pitch_names': self.pitch_names
    })
serializable.add(Track)

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
  # track serialization
  def serialize(self):
    return({ 
      'tracks': list(self)
    })
serializable.add(TrackList)

# represent a directed patch bay that routes between two lists
class PatchBay(observable.Object):
  def __init__(self, connections=None):
    observable.Object.__init__(self)
    if (connections is None):
      connections = set()
    self._connections = connections
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
  def serialize(self):
    return({
      'connections': list(self._connections)
    })
serializable.add(PatchBay)

# a transport to keep track of timepoints, playback, and recording
class Transport(observable.Object):
  def __init__(self, time=0.0, cycling=False, marks=None):
    observable.Object.__init__(self)
    # set up internal state
    self._playing = False
    self._recording = False
    self._cycling = cycling
    # store the time
    self._time = time
    self._last_played_to = time
    self._last_display_update = 0
    self._start_time = None
    # keep a timer that updates when the time is running
    self._run_timer = None
    # the minimum time resolution to send display updates
    self.display_interval = 0.05 # seconds
    # store all time marks
    if (marks is None):
      marks = [ ]
    self.marks = marks
    # the start and end times of the cycle region, which will default
    #  to the next and previous marks if not set externally
    self._cycle_start_time = None
    self.cycle_start_time = None
    self._cycle_end_time = None
    self.cycle_end_time = None
    # the amount to change time by when the skip buttons are pressed
    self.skip_delta = 1.0 # seconds
  # add methods for easy button binding
  def play(self, *args):
    self.playing = True
  def record(self, *args):
    self.recording = True
  def stop(self, *args):
    self.playing = False
    self.recording = False
  # whether play mode is on
  @property
  def playing(self):
    return(self._playing)
  @playing.setter
  def playing(self, value):
    value = (value == True)
    if (self._playing != value):
      self.recording = False
      self._playing = value
      if (self.playing):
        self._run()
      else:
        self._stop()
      self.on_change()
  # whether record mode is on
  @property
  def recording(self):
    return(self._recording)
  @recording.setter
  def recording(self, value):
    value = (value == True)
    if (self._recording != value):
      self.playing = False
      self._recording = value
      if (self.recording):
        self._run()
      else:
        self._stop()
      self.on_change()
  # whether cycle mode is on
  @property
  def cycling(self):
    return(self._cycling)
  @cycling.setter
  def cycling(self, value):
    value = (value == True)
    if (self._cycling != value):
      self.update_cycle_bounds()
      self._cycling = value
      self.on_change()
  # get the current timepoint of the transport
  @property
  def time(self):
    t = self._time
    if (self._start_time is not None):
      t += time.clock() - self._start_time
    return(t)
  @time.setter
  def time(self, t):
    # don't allow the time to be set while recording
    if (self._recording): return
    self._time = max(0.0, t)
    if (self._start_time is not None):
      self._start_time = time.clock()
    self.update_cycle_bounds()
    self.on_change()
  # start the time moving forward
  def _run(self):
    self._start_time = time.clock()
    self._last_played_to = self._time
    # establish the cycle region
    self.update_cycle_bounds()
    # start the update timer
    if (self._run_timer is None):
      self._run_timer = GLib.idle_add(self.on_running)
  # stop the time moving forward
  def _stop(self):
    self._time = self.time
    self._start_time = None
    if (self._run_timer is not None):
      GLib.source_remove(self._run_timer)
      self._run_timer = None
  def on_running(self):
    current_time = self.time
    # do cycling
    if ((self.cycling) and (self._cycle_end_time is not None) and 
        (current_time > self._cycle_end_time)):
      # only play up to the cycle end time
      self.on_play_to(self._cycle_end_time)
      # bounce back to the start, maintaining any interval we went past the end
      self._last_played_to = self._cycle_start_time
      current_time = (self._cycle_start_time + 
        (current_time - self._cycle_end_time))
      self.time = current_time
    # play up to the current time
    self.on_play_to(current_time)
    # notify for a display update if the minimum interval has passed
    abs_time = time.clock()
    elapsed = abs_time - self._last_display_update
    if (elapsed >= self.display_interval):
      self.on_change()
      self._last_display_update = abs_time
    return(True)
  # handle the playback of the span after and including self._last_played_to
  #  and up to but not including the given time
  def on_play_to(self, end_time):
    # prepare for the next range
    self._last_played_to = end_time
  # set the cycle region based on the current time
  def update_cycle_bounds(self):
    current_time = self.time
    if (self.cycle_start_time is not None):
      self._cycle_start_time = self.cycle_start_time
    else:
      self._cycle_start_time = self.get_previous_mark(current_time + 0.001)
    if (self.cycle_end_time is not None):
      self._cycle_end_time = self.cycle_end_time
    else:
      self._cycle_end_time = self.get_next_mark(current_time)
  # skip forward or back in time
  def skip_back(self, *args):
    self.time = self.time - self.skip_delta
  def skip_forward(self, *args):
    self.time = self.time + self.skip_delta
  # toggle a mark at the current time
  def toggle_mark(self, *args):
    t = self.time
    if (t in self.marks):
      self.marks.remove(t)
    else:
      self.marks.append(t)
      self.marks.sort()
    self.on_change()
  # return the time of the next or previous mark relative to a given time
  def get_previous_mark(self, from_time):
    for t in reversed(self.marks):
      if (t < from_time):
        return(t)
    # if we're back past the first mark, treat the beginning 
    #  like a virtual mark
    return(0)
  def get_next_mark(self, from_time):
    for t in self.marks:
      if (t > from_time):
        return(t)
    return(None)
  # move to the next or previous mark
  def previous_mark(self, *args):
    t = self.get_previous_mark(self.time)
    if (t is not None):
      self.time = t
  def next_mark(self, *args):
    t = self.get_next_mark(self.time)
    if (t is not None):
      self.time = t
  # transport serialization
  def serialize(self):
    return({
      'time': self.time,
      'cycling': self.cycling,
      'marks': self.marks
    })
serializable.add(Transport)

# make a time-to-pixel mapping with observable changes
class TimeScale(observable.Object):
  def __init__(self, pixels_per_second=24, time_offset=0.0):
    observable.Object.__init__(self)
    self._pixels_per_second = pixels_per_second
    self._time_offset = time_offset
  @property
  def pixels_per_second(self):
    return(self._pixels_per_second)
  @pixels_per_second.setter
  def pixels_per_second(self, value):
    if (value != self._pixels_per_second):
      self._pixels_per_second = float(value)
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
  def serialize(self):
    return({
      'pixels_per_second': self.pixels_per_second,
      'time_offset': self.time_offset
    })
serializable.add(TimeScale)

# represent a document, which can contain multiple tracks
class Document(Model):
  def __init__(self, tracks=None, transport=None, time_scale=None,
               input_patch_bay=None, output_patch_bay=None):
    Model.__init__(self)
    # tracks
    if (tracks is None):
      tracks = TrackList()
    self.tracks = tracks
    self.tracks.add_observer(self.on_change)
    # inputs
    if (input_patch_bay is None):
      input_patch_bay = PatchBay()
    self.input_patch_bay = input_patch_bay
    self.input_patch_bay.add_observer(self.on_input_change)
    # outputs
    if (output_patch_bay is None):
      output_patch_bay = PatchBay()
    self.output_patch_bay = output_patch_bay
    self.output_patch_bay.add_observer(self.on_output_change)
    # transport
    if (transport is None):
      transport = Transport()
    self.transport = transport
    # time scale
    if (time_scale is None):
      time_scale = TimeScale()
    self.time_scale = time_scale
  
  # add a track to the document
  def add_track(self, *args):
    self.tracks.append(Track())
  
  # connect input adapters when they're routed to something in the patch bay
  def on_input_change(self):
    for adapter in self.input_patch_bay.from_items:
      if (not adapter.is_connected):
        adapter.connect()
  # connect output adapters when there's something routed to them
  def on_output_change(self):
    for adapter in self.output_patch_bay.to_items:
      if (not adapter.is_connected):
        adapter.connect()
  # document serialization
  def serialize(self):
    return({ 
      'tracks': self.tracks,
      'transport': self.transport,
      'time_scale': self.time_scale,
      'input_patch_bay': self.input_patch_bay,
      'output_patch_bay': self.output_patch_bay
    })
serializable.add(Document)

