# coding=utf-8

import time
import yaml
import copy
import jackpatch

from PySide.QtCore import Signal, QTimer

from ..common import observable, serializable
from core import Model, ModelList
import unit
from ..midi.core import DeviceAdapterList, InputHandler

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

# interprets note and control channel messages and adds them to a track
class TrackInputHandler(InputHandler):
  def __init__(self, port, track, transport=None):
    InputHandler.__init__(self, port=port, target=track)
    # listen to a transport so we know when we're recording
    self._transport = None
    self.transport = transport
    # listen to the target so we know when it's armed
    if (self.target):
      self.target.add_observer(self.on_state_change)
    # hold a set of notes for all "voices" currently playing, keyed by pitch
    self._playing_notes = dict()
    # make a block to place recorded notes into
    self._target_block = None
  # listen for when the transport state changes
  @property
  def transport(self):
    return(self._transport)
  @transport.setter
  def transport(self, value):
    if (value is not self._transport):
      if (self._transport):
        self._transport.remove_observer(self.on_state_change)
      self._transport = value
      if (self._transport):
        self._transport.add_observer(self.on_state_change)
      self.on_state_change()
  # when the transport is recording and the track is armed, make a block to 
  #  record notes into and remove it otherwise
  def on_state_change(self):
    # determine whether we should be recording notes
    record = ((self.transport is not None) and (self.transport.recording) and 
              (self.target is not None) and (self.target.arm))
    # create and destroy the target block when the recording state changes
    if ((record) and (self._target_block is None)):
      self._target_block = Block(EventList(), time=self.transport.time)
      self.target.append(self._target_block)
    elif ((not record) and (self._target_block is not None)):
      duration = max(0, self.transport.time - self._target_block.time)
      self._target_block.duration = duration
      self._target_block.events.duration = duration
      self._target_block = None
    # extend the target block when the transport time changes
    current_time = self.transport.time
    base_time = 0.0
    if (self._target_block):
      base_time = self._target_block.time
      self._target_block.duration = max(
        self._target_block.duration, current_time - base_time)
    # extend open notes when the transport time changes
    for note in self._playing_notes.itervalues():
      note.duration = max(note.duration, 
        current_time - (base_time + note.time))
  @property
  def playing_notes(self):
    return(self._playing_notes.values())
  def end_all_notes(self):
    self._playing_notes = dict()
  # interpret messages
  def handle_message(self, data, time):
    if (len(data) != 3): return
    (status, data1, data2) = data
    kind = (status & 0xF0) >> 4
    channel = (status & 0x0F)
    # get the start time of the target block, if any
    base_time = 0.0
    if (self._target_block is not None):
      base_time = self._target_block.time
    # get note on/off messages
    if ((kind == 0x08) or (kind == 0x09)):
      pitch = data1
      velocity = data2 / 127.0
      # note on
      if (kind == 0x09):
        note = Note(time=(time - base_time), 
                    pitch=pitch, velocity=velocity, duration=0)
        self._playing_notes[pitch] = note
        if (self._target_block is not None):
          self._target_block.events.append(note)
      # note off
      elif (kind == 0x08):
        try:
          note = self._playing_notes[pitch]
        # this indicates a note-off with no prior note-on, not a big deal
        except KeyError: return
        note.duration = max(0, time - (base_time + note.time))
        del self._playing_notes[pitch]
    # report unexpected messages
    else:
      print('Unhandled message type %02X' % status)

# represent a track, which can contain multiple blocks
class Track(unit.Source, unit.Sink, ModelList):

  # names of the cyclical pitch classes starting at MIDI note 0
  PITCH_CLASS_NAMES = ( 
    u'C', u'D♭', u'D', u'E♭', u'E', u'F', 
    u'F♯', u'G', u'A♭', u'A', u'B♭', u'B' )

  def __init__(self, blocks=(), duration=60, name='Track',
                     solo=False, mute=False, arm=False,
                     level=1.0, pan=0.0, pitch_names=None,
                     transport=None):
    ModelList.__init__(self, blocks)
    unit.Source.__init__(self)
    unit.Sink.__init__(self)
    self._sink_type = 'midi'
    self._source_type = 'midi'
    self._name = name
    self._duration = duration
    self._solo = solo
    self._mute = mute
    self._arm = arm
    self._level = level
    self._pan = pan
    if (pitch_names is None): 
      pitch_names = dict()
    self._pitch_names = pitch_names
    # make a client and ports to connect to JACK
    self._client = jackpatch.Client('jackdaw-track')
    self._client.activate()
    self.source_port = jackpatch.Port(client=self._client, 
      name='playback',
      flags=jackpatch.JackPortIsOutput)
    self.sink_port = jackpatch.Port(client=self._client, 
      name='capture',
      flags=jackpatch.JackPortIsInput)
    # add a handler for incoming notes
    self._transport = transport
    self._input_handler = TrackInputHandler(
      port=self.sink_port, track=self, transport=self.transport)
  # invalidate cached data
  def invalidate(self):
    self._pitches = None
    self._times = None
    # whether the track is enabled for playback 
    # (this will be controlled by the track list)
    self.enabled = True
  # get and set the name of the track
  @property
  def name(self):
    return(self._name)
  @name.setter
  def name(self, value):
    if (value != self._name):
      self._name = value
      self.on_change()
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
  # get and set the time transport the track is placed on
  @property
  def transport(self):
    return(self._transport)
  @transport.setter
  def transport(self, value):
    if (value != self._transport):
      self._transport = value
      self._input_handler.transport = self._transport
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
    if (self._pitches is None):
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
      'name': self.name,
      'blocks': list(self),
      'duration': self.duration,
      'solo': self.solo,
      'mute': self.mute,
      'arm': self.arm,
      'level': self.level,
      'pan': self.pan,
      'pitch_names': self.pitch_names,
      'transport': self.transport
    })
serializable.add(Track)

# represent a list of tracks
class TrackList(ModelList):
  def __init__(self, tracks=(), transport=None):
    ModelList.__init__(self, tracks)
    self._transport = transport
    self.on_change()
  # add a track to the list
  def add_track(self):
    self.append(Track(duration=self.duration))
  # transfer global track state to the tracks
  def on_change(self):
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
    # bind all tracks to the transport
    for track in self:
      track.transport = self.transport
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
  # get and set the transport
  @property
  def transport(self):
    return(self._transport)
  @transport.setter
  def transport(self, value):
    if (value is not self._transport):
      self._transport = value
      self.on_change()
  # track serialization
  def serialize(self):
    return({ 
      'tracks': list(self),
      'transport': self.transport
    })
serializable.add(TrackList)

# a transport to keep track of timepoints, playback, and recording
class Transport(observable.Object):
  # regular init stuff
  def __init__(self, time=0.0, cycling=False, marks=None):
    observable.Object.__init__(self)
    # get a bridge to the JACK transport
    self._client = jackpatch.Client('jackdaw-transport')
    self._transport = jackpatch.Transport(client=self._client)
    # make a timer to update the transport model when the time changes
    self._update_timer = QTimer(self)
    self._update_timer.setInterval(500)
    self._update_timer.timeout.connect(self.update)
    # set up internal state
    self._recording = False
    self._cycling = cycling
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
    # store the time
    self._local_time = None
    self.time = time
    self._last_played_to = time
    self._last_display_update = 0
    self._start_time = None
    self._local_is_rolling = None
    # the amount to change time by when the skip buttons are pressed
    self.skip_delta = 1.0 # seconds
    # the amount of time to allow between updates of the display
    self.display_interval = 0.05 # seconds
    # start updating
    self._update_timer.start()
    self.update()
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
    return((self.is_rolling) and (not self.recording))
  @playing.setter
  def playing(self, value):
    value = (value == True)
    if (self.playing != value):
      self.recording = False
      if (value):
        self.start()
      else:
        self.pause()
      self.on_change()
  # whether record mode is on
  @property
  def recording(self):
    return((self.is_rolling) and (self._recording))
  @recording.setter
  def recording(self, value):
    value = (value == True)
    if (self._recording != value):
      self.playing = False
      self._recording = value
      if (self._recording):
        self.start()
      else:
        self.pause()
      self.on_change()
  # whether the transport is playing or recording
  @property
  def is_rolling(self):
    if (self._local_is_rolling is not None):
      return(self._local_is_rolling)
    return(self._transport.is_rolling)
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
    if (self._local_time is not None):
      return(self._local_time)
    return(self._transport.time)
  @time.setter
  def time(self, t):
    # don't allow the time to be set while recording
    if (self._recording): return
    # don't let the time be negative
    t = max(0.0, t)
    # record the local time setting so we can use it while the transport 
    #  updates to the new location
    self._local_time = t
    self._transport.time = t
    self.update_cycle_bounds()
    self.on_change()
  # start the time moving forward
  def start(self):
    self._last_played_to = self.time
    # establish the cycle region
    self.update_cycle_bounds()
    self._local_is_rolling = True
    self._transport.start()
    self.update()
  # stop time moving forward
  def pause(self):
    self._local_is_rolling = False
    self._transport.stop()
    self.update()
  def update(self):
    # clear the locally stored settings because now we're checking 
    #  the real transport
    self._local_time = None
    is_rolling = self.is_rolling
    self._local_is_rolling = None
    current_time = self.time
    # update infrequently when not running and frequently when running
    if (not is_rolling):
      if (self._update_timer.interval() != 500):
        self._update_timer.setInterval(500)
        self.on_change()
    else:
      if (self._update_timer.interval() != 50):
        self._update_timer.setInterval(50)
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
    elapsed = current_time - self._last_display_update
    if (abs(elapsed) >= self.display_interval):
      self.on_change()
      self._last_display_update = current_time
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

# make a units-to-pixels mapping with observable changes
class ViewScale(observable.Object):
  def __init__(self, pixels_per_second=24, pitch_height=16, time_offset=0.0):
    observable.Object.__init__(self)
    self._pixels_per_second = pixels_per_second
    self._time_offset = time_offset
    self._pitch_height = pitch_height
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
      'time_offset': self.time_offset,
      'pitch_height': self.pitch_height
    })
  def height_of_track(self, track):
    return(max(4, len(track.pitches)) * self.pitch_height)
  def track_spacing(self):
    return(6.0)
serializable.add(ViewScale)

# represent a document, which can contain multiple tracks
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
    # tracks
    if (tracks is None):
      tracks = TrackList(transport=self.transport)
    self.tracks = tracks
    self.tracks.add_observer(self.on_change)
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
      units = unit.UnitList()
      units.append(unit.MultitrackUnit(
        name='Tracks',
        tracks=self.tracks, 
        width=400,
        view_scale=self.view_scale, 
        transport=self.transport))
      units.append(unit.DeviceListUnit(
        name='Inputs',
        devices=self.devices, 
        require_input=False,
        require_output=True,
        x=-400))
    self.units = units
    self.units.add_observer(self.on_change)
    # a list of connections between units
    if (patch_bay is None):
      patch_bay = unit.PatchBay()
    self.patch_bay = patch_bay
    self.patch_bay.add_observer(self.on_change)
    
  # save the document to a file
  def save(self):
    output_stream = open(self.path, 'w')
    output_stream.write(yaml.dump(self))
    output_stream.close()
  # document serialization
  def serialize(self):
    return({
      'devices': self.devices,
      'tracks': self.tracks,
      'transport': self.transport,
      'view_scale': self.view_scale,
      'units': self.units,
      'patch_bay': self.patch_bay
    })
serializable.add(Document)

