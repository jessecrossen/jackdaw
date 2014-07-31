import sys

import observable

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
  def __init__ (self, value=None):
    observable.List.__init__(self)
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

# represents a series of events grouped into a logical block with a duration
class EventList(ModelList):
  def __init__(self, duration=60, divisions=1):
    ModelList.__init__(self)
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
    self.events = events
    self.events.add_listener(self.on_change)
    self._time = time
    self._duration = duration
  
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
      for time in self.events.times:
        times.add(time)
        repeat_time = self.events.duration
        if (repeat_time > 0):
          time += repeat_time
          while (time < self.duration):
            times.add(time)
            time += repeat_time
      self._times = list(times)
      self._times.sort()
    return(self._times)
  # get all pitch classes within the block
  @property
  def pitches(self):
    return(self.events.pitches)
  
# represent a track, which can contain multiple blocks
class Track(ModelList):
  def __init__(self, duration=60):
    ModelList.__init__(self)
    self._duration = duration
    self._enabled = True
    self._armed = False
    
  # invalidate cached data
  def invalidate(self):
    self._pitches = None
    self._times = None
    
  # the total length of time of the track content (in seconds)
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (self._duration != value):
      self._duration = value
      self.on_change()
  # whether the track is enabled for playback
  @property
  def enabled(self):
    return(self._enabled)
  @enabled.setter
  def enabled(self, value):
    value = (value == True)
    if (self._enabled != value):
      self._enabled = value
      self.on_change()
  # whether the track is armed for recording
  @property
  def armed(self):
    return(self._armed)
  @armed.setter
  def armed(self, value):
    value = (value == True)
    if (self._armed != value):
      self._armed = value
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
  def __init__(self):
    ModelList.__init__(self)
  
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

# represent a document, which can contain multiple tracks
class Document(Model):
  def __init__(self):
    Model.__init__(self)
    self.tracks = TrackList()
    self.tracks.add_listener(self.on_change)
    
