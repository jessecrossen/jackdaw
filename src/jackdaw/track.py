# coding=utf-8

import math
import jackpatch

import observable
import serializable
from model import Model, ModelList
import block
import midi
import unit

# represent a track, which can contain multiple blocks
class Track(unit.Source, unit.Sink, ModelList):

  # names of the cyclical pitch classes starting at MIDI note 0
  PITCH_CLASS_NAMES = ( 
    u'C', u'D♭­', u'D', u'E♭­', u'E', u'F', 
    u'F♯', u'G', u'A♭­', u'A', u'B♭­', u'B' )

  def __init__(self, blocks=(), name='Track',
                     solo=False, mute=False, arm=False,
                     pitch_names=None, controller_names=None, 
                     controller_outputs=None,
                     bend_range=6.0,
                     transport=None):
    ModelList.__init__(self, blocks)
    unit.Source.__init__(self)
    unit.Sink.__init__(self)
    self._sink_type = 'midi'
    self._source_type = 'midi'
    self._name = name
    self._solo = solo
    self._mute = mute
    self._arm = arm
    self._bend_range = bend_range
    if (pitch_names is None): 
      pitch_names = dict()
    self._pitch_names = pitch_names
    if (controller_names is None): 
      controller_names = dict()
    self._controller_names = controller_names
    # make a list of controller values that input has been received from,
    #  keyed by controller number
    self._controller_values = dict()
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
    # add a handler for playback
    self._output_handler = TrackOutputHandler(
      port=self.source_port, track=self, transport=self.transport)
    # keep track of ports connected for previewing track input
    self._connected_sources = dict()
    self._connected_sinks = dict()
    self.add_observer(self.update_passthru)
    # make a list of controller output handlers, keyed by number
    self._controller_outputs = dict()
    if (controller_outputs is not None):
      for output in controller_outputs:
        output.client = self._client
        self._controller_outputs[output.number] = output
  # invalidate cached data
  def invalidate(self):
    self._max_time = None
    self._pitches = None
    self._controllers = None
    self._times = None
    self._snap_times = None
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
  # get and set the +/- range of 14-bit pitch bend values in semitones
  @property
  def bend_range(self):
    return(self._bend_range)
  @bend_range.setter
  def bend_range(self, value):
    if (value != self._bend_range):
      self._bend_range = value
      self.on_change()
      self.send_bend_range()
  # send the current pitch bend range to the midi output port
  def send_bend_range(self):
    port = self.source_port
    semitones = int(math.floor(self._bend_range))
    cents = int(math.floor((self._bend_range - semitones) * 100.0))
    for channel in range(0, 16):
      cc = 0xB0 | channel
      port.send((cc, 0x65, 0x00))
      port.send((cc, 0x64, 0x00))
      port.send((cc, 0x06, semitones))
      port.send((cc, 0x26, cents))
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
  # get and set user-defined names for control change numbers
  @property
  def controller_names(self):
    return(self._controller_names)
  @controller_names.setter
  def controller_names(self, value):
    self._controller_names = value
    self.on_change()
  # get a name for a control change number
  def name_of_controller(self, number):
    # see if there's a user-defined mapping for it
    if (number in self._controller_names):
      return(self._controller_names[number])
    # otherwise look it up in the list of pitch classes
    return('CC %d' % number)
  # get the cached value of the given controller, or None if there isn't one
  def value_of_controller(self, number):
    try:
      return(self._controller_values[number])
    except KeyError: return(None)
  # get an output handler for a controller
  def output_for_controller(self, number):
    if (number not in self._controller_outputs):
      self._controller_outputs[number] = ControllerTrackOutput(
        client=self._client, number=number, 
        value=self.value_of_controller(number))
    return(self._controller_outputs[number])
  # get a list of output handlers for the current set of controllers
  @property
  def controller_outputs(self):
    outputs = list()
    for number in self.controllers:
      outputs.append(self.output_for_controller(number))
    return(outputs)
  # the total length of time of the track content (in seconds)
  @property
  def duration(self):
    if (self._max_time is None):
      self._max_time = 0.0
      for block in self:
        self._max_time = max(self._max_time, block.time + block.duration)
    return(self._max_time)
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
      # clear stored controller values when the track is disarmed
      if (not self._arm):
        self._controller_values = dict()
      self.on_change()
  # get whether the track's inputs are being previewed
  @property
  def previewing(self):
    return(self.arm and self.enabled)
  # get and set the time transport the track is placed on
  @property
  def transport(self):
    return(self._transport)
  @transport.setter
  def transport(self, value):
    if (value != self._transport):
      self._transport = value
      self._input_handler.transport = self._transport
      self._output_handler.transport = self._transport
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
  # get a list of snappable times (i.e. times of non-selected events)
  @property
  def snap_times(self):
    if (self._snap_times == None):
      times = set()
      for block in self:
        # add the snap times of all events in the block
        for time in block.snap_times:
          times.add(block.time + time)
      self._snap_times = list(times)
      self._snap_times.sort()
    return(self._snap_times)
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
  # update the cached value of a controller
  def update_controller_value(self, number, value):
    self._controller_values[number] = value
    self.output_for_controller(number).value = value
    self.on_change()
  # get a list of unique controller numbers for control change messages 
  #  recorded on this track
  @property
  def controllers(self):
    if (self._controllers is None):
      controllers = set()
      for block in self:
        for controller in block.controllers:
          controllers.add(controller)
      for controller in self._controller_values.keys():
        controllers.add(controller)
      self._controllers = list(controllers)
      self._controllers.sort()
    return(self._controllers)
  # make connections through the track
  def update_passthru(self):
    # get previously connected ports
    old_sources = self._connected_sources
    old_sinks = self._connected_sinks
    # get connected ports
    new_sources = dict()
    if ((self._sink_port is not None) and (self.previewing)):
      for port in self._sink_port.get_connections():
        if (port.name in old_sources):
          new_sources[port.name] = old_sources[port.name]
        else:
          new_sources[port.name] = port
    new_sinks = dict()
    if ((self._source_port is not None) and (self.previewing)):
      for port in self._source_port.get_connections():
        if (port.name in old_sinks):
          new_sinks[port.name] = old_sinks[port.name]
        else:
          new_sinks[port.name] = port
    # update the set of connected ports
    self._connected_sources = new_sources
    self._connected_sinks = new_sinks
    # convert dicts to sets for easy differencing
    old_sources = set(old_sources.values())
    old_sinks = set(old_sinks.values())
    new_sources = set(new_sources.values())
    new_sinks = set(new_sinks.values())
    # remove old connections
    remove_sources = old_sources.difference(new_sources)
    remove_sinks = old_sinks.difference(new_sinks)
    for source in remove_sources:
      for sink in old_sinks:
        self._client.disconnect(source, sink)
    for sink in remove_sinks:
      for source in old_sources:
        self._client.disconnect(source, sink)
    # add new connections
    add_sources = new_sources.difference(old_sources)
    add_sinks = new_sinks.difference(old_sinks)
    for source in add_sources:
      for sink in new_sinks:
        self._client.connect(source, sink)
    for sink in add_sinks:
      for source in new_sources:
        self._client.connect(source, sink)
  # track serialization
  def serialize(self):
    return({ 
      'name': self.name,
      'blocks': list(self),
      'solo': self.solo,
      'mute': self.mute,
      'arm': self.arm,
      'pitch_names': self.pitch_names,
      'bend_range': self.bend_range,
      'controller_names': self.controller_names,
      'controller_outputs': self.controller_outputs,
      'transport': self.transport
    })
serializable.add(Track)

# represent a controller's output on a track
class ControllerTrackOutput(unit.Source, Model):
  def __init__(self, number, value=0.0, client=None):
    self._client = None
    self._number = number
    self._value = 0.0
    Model.__init__(self)
    unit.Source.__init__(self)
    self._source_type = 'midi'
    self.client = client
    self.value = value
  @property
  def client(self):
    return(self._client)
  @client.setter
  def client(self, client):
    if ((client is not None) and (self.source_port is None)):
      self._client = client
      self.source_port = jackpatch.Port(client=self._client,
        name=('CC %d' % self._number), flags=jackpatch.JackPortIsOutput)
  @property
  def number(self):
    return(self._number)
  @property
  def value(self):
    return(self._value)
  @value.setter
  def value(self, value):
    if ((value is not None) and (value != self._value)):
      self._value = value
      self.on_change()
      self.send_value(self._value)
  # send a midi message to propagate the current value
  def send_value(self, value, time=0.0):
    self._value = value
    if (self.source_port is not None):
      self.source_port.send(
        (0xB0, self._number, int(round(value * 127.0))), time)
  def serialize(self):
    return({
      'number': self.number,
      'value': self.value
    })
serializable.add(ControllerTrackOutput)

# represent a list of tracks
class TrackList(ModelList):
  def __init__(self, tracks=(), transport=None):
    ModelList.__init__(self, tracks)
    self._transport = transport
    self.on_change()
  # add a track to the list
  def add_track(self):
    self.append(Track())
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
    self._snap_times = None
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
  # get a list of unique times for all non-selected events in these tracks
  @property
  def snap_times(self):
    if (self._snap_times == None):
      times = set()
      for track in self:
        for time in track.snap_times:
          times.add(time)
      self._snap_times = list(times)
      self._snap_times.sort()
    return(self._snap_times)
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
class SequencerUnit(unit.Unit):
  def __init__(self, tracks, view_scale, transport, *args, **kwargs):
    unit.Unit.__init__(self, *args, **kwargs)
    self.tracks = tracks
    self.tracks.add_observer(self.on_change)
    self.transport = transport
    self.view_scale = view_scale
    self.view_scale.add_observer(self.on_change)
  @property
  def model_refs(self):
    return((self.tracks, self.transport, self.view_scale))
  def serialize(self):
    obj = unit.Unit.serialize(self)
    obj['tracks'] = self.tracks
    obj['transport'] = self.transport
    obj['view_scale'] = self.view_scale
    return(obj)
serializable.add(SequencerUnit)

# interprets note and control channel messages and adds them to a track
class TrackInputHandler(midi.InputHandler):
  def __init__(self, port, track, transport=None):
    self._in_state_change = False
    midi.InputHandler.__init__(self, port=port, target=track)
    # make a placeholder for a block to place recorded notes into
    self._target_block = None
    # hold a set of notes for all "voices" currently playing, keyed by pitch
    self._playing_notes = dict()
    # hold a set of bend values keyed by channel for global bend
    self._channel_bends = dict()
    # hold a set of controller numbers we've received input for
    self._active_controllers = set()
    # listen to a transport so we know when we're recording
    self._transport = None
    self.transport = transport
    # listen to the target so we know when it's armed
    if (self.target):
      self.target.add_observer(self.on_state_change)
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
    # prevent infinite recursion
    if (self._in_state_change): return
    self._in_state_change = True
    # determine whether we should be recording notes
    record = ((self.transport is not None) and (self.transport.recording) and 
              (self.target is not None) and (self.target.arm))
    # create and destroy the target block when the recording state changes
    if ((record) and (self._target_block is None)):
      self._target_block = block.Block(block.EventList(), time=self.transport.time)
      self.target.append(self._target_block)
    elif ((not record) and (self._target_block is not None)):
      # receive all queued events
      self.receive(limit_time=False)
      duration = max(0, self.transport.time - self._target_block.time)
      self._target_block.duration = duration
      self._target_block.events.duration = duration
      self._target_block = None
      self._channel_bends = dict()
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
    self._in_state_change = False
  @property
  def playing_notes(self):
    return(self._playing_notes.values())
  def end_all_notes(self):
    self._playing_notes = dict()
    self._active_controllers = set()
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
    if ((kind == 0x8) or (kind == 0x9)):
      pitch = data1
      velocity = data2 / 127.0
      # note on
      if ((kind == 0x9) and (velocity > 0.0)):
        note = block.Note(time=(time - base_time), 
                    pitch=pitch, velocity=velocity, duration=0)
        note.channel = channel
        # add initial pitch bend if there is any on the note's channel
        if (channel in self._channel_bends):
          channel_bend = self._channel_bends[channel]
          if (channel_bend != 0.0):
            note.add_bend(0.0, channel_bend)
        self._playing_notes[pitch] = note
        if (self._target_block is not None):
          self._target_block.events.append(note)
      # note off
      elif ((kind == 0x8) or (velocity == 0.0)):
        try:
          note = self._playing_notes[pitch]
        # this indicates a note-off with no prior note-on, not a big deal
        except KeyError: return
        note.duration = max(0, time - (base_time + note.time))
        # cap the bend and velocity curves, if any
        if (len(note.bend) > 0):
          note.add_bend(note.duration, note.bend[-1][1])
        if (len(note.aftertouch) > 0):
          note.add_aftertouch(note.duration, note.aftertouch[-1][1])
        # remove the note from the list of playing notes
        del self._playing_notes[pitch]
    # polyphonic aftertouch
    elif (kind == 0xA):
      pitch = data1
      velocity = data2 / 127.0
      if (pitch in self._playing_notes):
        note = self._playing_notes[pitch]
        # make sure the note's velocity curve has fixed endpoints
        #  for optimized drawing routines
        if (len(note.aftertouch) == 0):
          note.add_aftertouch(0.0, note.velocity)
        note.add_aftertouch(time - (base_time + note.time), velocity)
    # pitch bend
    elif (kind == 0xE):
      bend = (float(0x2000 - ((data2 << 7) | data1)) / float(0x2000))
      bend *= (self.target.bend_range / 2.0)
      self._channel_bends[channel] = bend
      # if the playing notes have multiple channels, assume we're using a 
      #  channel rotation scheme for polyphonic pitch bends
      notes_by_channel = dict()
      for note in self._playing_notes.itervalues():
        if (note.channel == channel):
          # make sure the note's bend curve has fixed endpoints
          #  for optimized drawing routines
          if (len(note.bend) == 0):
            note.add_bend(0.0, 0.0)
          note.add_bend(time - (base_time + note.time), bend)
    # get control channel messages
    elif (kind == 0xB):
      number = data1
      value = (data2 / 127.0)
      ccset = block.CCSet(time=(time - base_time), number=number, value=value)
      if (self._target_block is not None):
        self._target_block.events.append(ccset)
        # add the initial value at the beginning of the block if this 
        #  is the first value for this controller
        if (number not in self._active_controllers):
          self._active_controllers.add(number)
          self._target_block.events.append(block.CCSet(
            time=0.0, number=number, value=value))
      if (self.target.arm):
        self.target.update_controller_value(number, value)

class TrackOutputHandler(observable.Object):
  def __init__(self, port, track, transport):
    observable.Object.__init__(self)
    # keep local track of whether playback is engaged
    self._playing = False
    # the time events have been scheduled up to (non-inclusive)
    self._scheduled_to = None
    # the amount of time to schedule events into the future
    self.min_schedule_ahead = 0.5
    self.max_schedule_ahead = 1.0
    # a dict mapping notes to the times at which 
    #  each note should stop playing
    self._note_ends = dict()
    # dict mapping channel numbers to the current pitch bend on that channel
    self._channel_bends = dict()
    self.port = port
    self.track = track
    self._transport = None
    self.transport = transport
  # listen for when the transport state changes
  @property
  def transport(self):
    return(self._transport)
  @transport.setter
  def transport(self, value):
    if (value is not self._transport):
      if (self._transport):
        self._transport.remove_observer(self.on_transport_change)
      self._transport = value
      if (self._transport):
        self._transport.add_observer(self.on_transport_change)
        self.min_schedule_ahead = self._transport.update_interval
        self.max_schedule_ahead = 2.0 * self.min_schedule_ahead
      self.on_transport_change()
  def on_transport_change(self):
    playing = (self.transport.playing or self.transport.recording)
    if (playing != self._playing):
      self._playing = playing
      if (self._playing):
        self.start()
      else:
        self.stop()
    if (self._playing):
    
      # TODO: handle time jumps
    
      self.send()
  # start playback
  def start(self):
    # send initial values for track control channels
    self._send_initial_controller_values()
    # send pitch bend sensitivity to all channels
    self.track.send_bend_range()
    # initialize the scheduling time range
    self._scheduled_to = self.transport.time
  def _send_initial_controller_values(self):
    controller_values = dict()
    now = self.transport.time
    for block in self.track:
      if (block.time > now): continue
      for event in block.events:
        try:
          number = event.number
          value = event.value
          time = event.time
        except AttributeError: continue
        if (time > now): break
        controller_values[number] = value
    for (number, value) in controller_values.iteritems():
      self.track.output_for_controller(number).send_value(value, 0.0)
  # schedule some events for playback
  def send(self):
    # if the track is muted, stop current notes and don't send any more
    if (not self.track.enabled):
      self.end_all_notes()
      return
    # if we're already scheduled ahead enough, we're done
    now = self.transport.time
    if (self._scheduled_to is None):
      self._scheduled_to = now
    ahead = now - self._scheduled_to
    if (ahead > self.min_schedule_ahead): return
    # get the interval to schedule
    begin = self._scheduled_to
    end = now + self.max_schedule_ahead
    # schedule events into the future
    events = [ ]
    for block in self.track:
      bt = block.time
      # skip blocks that don't overlap the current time
      if ((bt > end) or (bt + block.duration <= begin)):
        continue
      # get the indices of the possible repeats of the block's events 
      #  that notes in this time range might fall into
      repeat = float(block.events.duration)
      begin_repeat = int(math.floor((begin - bt) / repeat))
      end_repeat = int(math.floor((end - bt) / repeat))
      # limit played notes to ones that start before the end of the block
      block_end = min(end, block.time + block.duration)
      # find events in the block that should be scheduled for a start
      for event in block.events:
        et = bt + (begin_repeat * repeat) + event.time
        if ((et >= begin) and (et < block_end)):
          events.append((event, et))
        # try the note in two places if the time range straddles 
        #  a repeat boundary
        if (end_repeat != begin_repeat):
          et = bt + (end_repeat * repeat) + event.time
          if ((et >= begin) and (et < block_end)):
            events.append((event, et))
    # schedule beginnings of events
    for (event, t1) in events:
      t2 = t1
      try:
        t2 += event.duration
      except AttributeError: pass
      pitch = None
      try:
        pitch = event.pitch
      except AttributeError: pass
      # start notes
      if (pitch is not None):
        velocity = 127
        try:
          velocity = int(math.floor(event.velocity * 127.0))
        except AttributeError: pass
        event.channel = len(self._note_ends) & 0xF
        # apply any initial pitch bend to the note
        if (len(event.bend) > 0):
          (bt, bend) = event.bend[0]
          if (bt != 0.0):
            bend = 0.0
          current_bend = 0.0
          if (event.channel in self._channel_bends):
            current_bend = self._channel_bends[event.channel]
          if (bend != current_bend):
            self._send_pitch_bend(event.channel, bend, t1 - now)
        # begin the note
        note_on = 0x90 | (event.channel & 0xF)
        self.port.send((note_on, pitch, velocity), t1 - now)
        self._note_ends[event] = t2
      # send control changes
      else:
        number = None
        value = None
        try:
          number = event.number
          value = event.value
        except AttributeError: pass
        else:
          self.track.output_for_controller(number).send_value(value, t1 - now)
    # schedule pitch bends and aftertouch in the current interval
    for (note, t) in self._note_ends.iteritems():
      st = t - note.duration
      for (bt, bend) in note.bend:
        bt += st
        if (bt >= begin) and (bt < end):
          self._send_pitch_bend(note.channel, bend, bt - now)
      for (at, velocity) in note.aftertouch:
        at += st
        if (at >= begin) and (at < end):
          aftertouch = 0xA0 | (note.channel & 0xF)
          self.port.send(
            (aftertouch, note.pitch, int(velocity * 127.0)), at - now)
    # schedule ending events if they are in the current interval
    note_ends = dict()
    for (note, t) in self._note_ends.iteritems():
      if ((t >= begin) and (t < end)):
        self._send_note_off(note, t - now)
      else:
        note_ends[note] = t
    self._note_ends = note_ends
    self._scheduled_to = end
  # send a note-off event
  def _send_note_off(self, note, time=0.0):
    note_off = 0x80 | (note.channel & 0xF)
    self.port.send((note_off, note.pitch, 0), time)
  # send a pitch bend
  def _send_pitch_bend(self, channel, bend, time):
    bend = bend * (float(0x4000) / self.track.bend_range)
    bend = min(max(0x0000, int(float(0x2000) + bend)), 0x4000)
    msb = (bend >> 7) & 0x7F
    lsb = bend & 0x7F
    pitch_bend = 0xE0 | (channel & 0xF)
    self.port.send((pitch_bend, lsb, msb), time)
    self._channel_bends[channel] = bend
  # schedule endings for all currently playing notes
  def end_all_notes(self):
    # clear any pending events in the send queue
    self.port.clear_send()
    for (note, t) in self._note_ends.iteritems():
      self._send_note_off(note, 0.0)
    # zero pitch bends on all channels
    for (channel, bend) in self._channel_bends.iteritems():
      if (bend != 0.0):
        self._send_pitch_bend(channel, 0.0, 0.0)
    self._note_ends = dict()
  # stop playback
  def stop(self):
    self.end_all_notes()