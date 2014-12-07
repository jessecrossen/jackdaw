import copy

import observable
import serializable
from model import Model, ModelList
 
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
    value = max(0.0, value)
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

# represents a single control-change message with time, controller number, 
#  and controller value
class CCSet(Model):
  def __init__(self, time=None, number=None, value=None):
    Model.__init__(self)
    self._time = time
    self._number = number
    self._value = value
  # the time relative to the beginning of its container when the 
  #  controller setting takes effect (in seconds)
  @property
  def time(self):
    return(self._time)
  @time.setter
  def time(self, value):
    value = max(0.0, value)
    if (self._time != value):
      self._time = value
      self.on_change()
  # a controller number from 0-119 identifying what is being controlled
  @property
  def number(self):
    return(self._number)
  @number.setter
  def number(self, value):
    if (self._number != value):
      self._number = value
      self.on_change()
  # a floating point number from 0-1 identifying the value 
  #  the controller is being set to
  @property
  def value(self):
    return(self._value)
  @value.setter
  def value(self, value):
    if (self._value != value):
      self._value = value
      self.on_change()
  # define a copy operation for control change messages
  def __copy__(self):
    return(CCSet(time=self.time, 
                 number=self.number,
                 value=self.value))
  def __repr__(self):
    return('CCSet(time=%0.9g, number=%d, value=%0.9g)' %
            (self.time, self.number, self.value))
  def serialize(self):
    return({ 
      'time': self.time,
      'number': self.number,
      'value': self.value
    })
serializable.add(CCSet)

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
    self._snap_times = None
    self._controllers = None
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
  # lazily get a list of unique controller numbers for control change messages 
  #  in the list
  @property
  def controllers(self):
    if (self._controllers == None):
      controllers = set()
      for event in self:
        if (hasattr(event, 'number')):
          controllers.add(event.number)
      self._controllers = list(controllers)
      self._controllers.sort()
    return(self._controllers)
  # lazily get a list of unique times for all notes in the list
  @property
  def times(self):
    if (self._times == None):
      times = set()
      for event in self:
        if (hasattr(event, 'time')):
          times.add(event.time)
          if (hasattr(event, 'duration')):
            times.add(event.time + event.duration)
      self._times = list(times)
      self._times.sort()
    return(self._times)
  # lazily get a list of unique times for all non-selected notes in the list
  @property
  def snap_times(self):
    if (self._snap_times == None):
      times = set()
      for event in self:
        if ((hasattr(event, 'time')) and 
            ((not hasattr(event, 'selected')) or (not event.selected))):
          times.add(event.time)
          if (hasattr(event, 'duration')):
            times.add(event.time + event.duration)
      self._snap_times = list(times)
      self._snap_times.sort()
    return(self._snap_times)
  # serialization
  def serialize(self):
    return({ 
      'events': list(self),
      'duration': self.duration,
    'divisions': self.divisions
    })
serializable.add(EventList)

# a placeholder model for manipulating the beginning of a block's events
class BlockStart(Model):
  def __init__(self, block):
    Model.__init__(self)
    self._block = block
  @property
  def time(self):
    return(self._block.time)
  @time.setter
  def time(self, value):
    duration = max(0.0, 
      (self._block.time + self._block.events.duration) - value)
    if (value != self._block.events.duration):
      delta = self._block.events.duration - duration
      min_event_time = None
      for event in self._block.events:
        if ((min_event_time is None) or (event.time < min_event_time)):
          min_event_time = event.time
      if ((delta > 0) and (delta > min_event_time)):
        delta = min_event_time
      if (delta != 0.0):
        for event in self._block.events:
          event.time -= delta
        self._block.events.duration -= delta
        self._block.time += delta
        self._block.duration -= delta
        
# a placeholder model for manipulating the duration of a block
class BlockEnd(Model):
  def __init__(self, block):
    Model.__init__(self)
    self._block = block
  @property
  def time(self):
    return(self._block.time + self._block.duration)
  @time.setter
  def time(self, value):
    duration = max(0.0, value - self._block.time)
    if (duration != self._block.duration):
      self._block.duration = duration
      self.on_change()
# a placeholder model for manipulating the repeat length of a block's events
class BlockRepeat(Model):
  def __init__(self, block):
    Model.__init__(self)
    self._block = block
  @property
  def time(self):
    return(self._block.events.duration)
  @time.setter
  def time(self, value):
    value = max(0.0, value)
    if (value != self._block.events.duration):
      self._block.events.duration = value
      self.on_change()

# represents a placement of an event list on a timeline with its own duration
# the event list is truncated or repeated to fill the duration
class Block(Model):
  def __init__(self, events, time=0, duration=0):
    Model.__init__(self)
    self._events = events
    self._events.add_observer(self.on_change)
    self._time = time
    self._duration = duration
    # make placeholders for manipulating the block
    self._start = BlockStart(self)
    self._end = BlockEnd(self)
    self._repeat = BlockRepeat(self)
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
  # expose placeholders as properties
  @property
  def start(self):
    return(self._start)
  @property
  def end(self):
    return(self._end)
  @property
  def repeat(self):
    return(self._repeat)
  # the time relative to the beginning of its container when the block 
  #  begins playing (in seconds)
  @property
  def time(self):
    return(self._time)
  @time.setter
  def time(self, value):
    value = max(0.0, value)
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
    self._snap_times = None
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
  # get all times of non-selected events in the block
  @property
  def snap_times(self):
    if (self._snap_times == None):
      times = set()
      repeat_time = self.events.duration
      event_times = set(self.events.snap_times)
      if (self.selected):
        event_times.add(0.0)
      for time in event_times:
        times.add(time)
        if (repeat_time > 0):
          time += repeat_time
          while (time < self.duration):
            times.add(time)
            time += repeat_time
      if (self.selected):
        times.add(self.duration)
      self._snap_times = list(times)
      self._snap_times.sort()
    return(self._snap_times)
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
  # get a list of unique controller numbers for control change messages 
  #  recorded on this block
  @property
  def controllers(self):
    return(self.events.controllers)
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