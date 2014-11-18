# coding=utf-8

import jackpatch

import observable
import serializable
from model import Model, ModelList
import block
import midi
import unit

# interprets note and control channel messages and adds them to a track
class TrackInputHandler(midi.InputHandler):
  def __init__(self, port, track, transport=None):
    midi.InputHandler.__init__(self, port=port, target=track)
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
      self._target_block = block.Block(block.EventList(), time=self.transport.time)
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
        note = block.Note(time=(time - base_time), 
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

# make a unit that represents the track list of the document
class MultitrackUnit(unit.Unit):
  def __init__(self, tracks, view_scale, transport, *args, **kwargs):
    unit.Unit.__init__(self, *args, **kwargs)
    self.tracks = tracks
    self.tracks.add_observer(self.on_change)
    self.transport = transport
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
  def serialize(self):
    obj = unit.Unit.serialize(self)
    obj['tracks'] = self.tracks
    obj['transport'] = self.transport
    obj['view_scale'] = self.view_scale
    return(obj)
serializable.add(MultitrackUnit)