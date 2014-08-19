import math
import time
import alsamidi

from gi.repository import GLib

from ..common import observable
from ..models import doc

# a transport controller to keep track of timepoints, playback, and recording
class Transport(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    # set up internal state
    self._playing = False
    self._recording = False
    self._cycling = False
    # store the time
    self._time = 0
    self._last_played_to = 0
    self._last_display_update = 0
    self._start_time = None
    # keep a timer that updates when the time is running
    self._run_timer = None
    # the minimum time resolution to send display updates
    self.display_interval = 0.05 # seconds
    # store all time marks
    self.marks = [ ]
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
    # TODO
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

# manages the manipulation of tracks and routing of events for recording
#  by coordinating a transport, input patch bay, and tracks
class Recorder(observable.Object):
  def __init__(self, transport, input_patch_bay, output_patch_bay):
    observable.Object.__init__(self)
    self._updating = False
    self.transport = transport
    self.transport.add_observer(self.on_transport_change)
    self.input_patch_bay = input_patch_bay
    self.input_patch_bay.add_observer(self.update)
    self.output_patch_bay = output_patch_bay
    self.output_patch_bay.add_observer(self.update)
    # track whether we've registered the start of recording
    self._recording = False
    # the transport time when recording started
    self._start_time = 0.0
    # hold a list of tracks mapped to the block on that track that's 
    #  receiving input
    self._preview_connections = set()
    self._tracks = set()
    self._active_inputs = set()
    self._active_tracks = set()
    self._active_blocks = dict()
  # handle changes to the state of the transport so we can start and stop 
  #  recording
  def on_transport_change(self):
    if (self.transport.recording != self._recording):
      self._recording = self.transport.recording
      if (self._recording):
        self.start()
      else:
        self.stop()
    # when recording, extend the durations of active blocks and playing notes
    if (self._recording):
      time = self.transport.time
      for block in self._active_blocks.itervalues():
        block.events.duration = time - block.time 
        block.duration = block.events.duration
      for active_input in self._active_inputs:
        try:
          notes = active_input.playing_notes
        except AttributeError: continue
        for note in notes:
          note.duration = active_input.time - note.time
  # handle changes to the patch bay so we can respect plugging and unplugging 
  #  during recording
  def update(self):
    if (self._updating): return
    self._updating = True
    # cache the transport time so all time operations below are synchronous
    time = self.transport.time
    # listen to all connected tracks for changes in the arm state
    tracks = set()
    for track in self.input_patch_bay.to_items:
      tracks.add(track)
    for track in self.output_patch_bay.from_items:
      tracks.add(track)
    new_tracks = tracks.difference(self._tracks)
    for track in new_tracks:
      track.add_observer(self.update)
    old_tracks = self._tracks.difference(tracks)
    for track in old_tracks:
      track.remove_observer(self.update)
    self._tracks = tracks
    # update active tracks, inputs, and preview connection lists
    active_tracks = set()
    active_inputs = set()
    preview_connections = set()
    tracks = self.input_patch_bay.to_items
    for track in tracks:
      if (track.arm):
        active_tracks.add(track)
        ins = self.input_patch_bay.items_connected_to(track)
        outs = self.output_patch_bay.items_connected_from(track)
        for i in ins:
          active_inputs.add(i)
          for o in outs:
            preview_connections.add((i, o))
    # end all pending notes for deactivated inputs
    deactivated_inputs = self._active_inputs.difference(active_inputs)
    for i in deactivated_inputs:
      i.remove_listener(self.on_event)
      i.end_all_notes()
    # connect to all newly-activated inputs
    activated_inputs = active_inputs.difference(self._active_inputs)
    for i in activated_inputs:
      i.add_listener(self.on_event)
      i.connect()
      # sync all newly-activated inputs to the current transport 
      #  time if recording
      if (self._recording):
        i.time = time - self._start_time
    self._active_inputs = active_inputs
    # close blocks for all disarmed tracks
    deactivated_tracks = self._active_tracks.difference(active_tracks)
    for t in deactivated_tracks:
      if (t in self._active_blocks):
        del self._active_blocks[t]
    # if recording, start blocks for all newly-activated tracks
    activated_tracks = active_tracks.difference(self._active_tracks)
    for t in activated_tracks:
      if ((self._recording) and (t not in self._active_blocks)):
        self.add_block_to_track(t, self._start_time)
    self._active_tracks = active_tracks
    # update input preview connections
    old_previews = self._preview_connections.difference(preview_connections)
    for (source, dest) in old_previews:
      alsamidi.disconnect_devices(source.device, dest.device)
    new_previews = preview_connections.difference(self._preview_connections)
    for (source, dest) in new_previews:
      alsamidi.connect_devices(source.device, dest.device)
    self._preview_connections = preview_connections
    self._updating = False
  # start recording
  def start(self):
    # get the current transport time so it's the same across tracks
    time = self._start_time = self.transport.time
    # make sure all active tracks have a block to record to
    for track in self._active_tracks:
      if (track not in self._active_blocks):
        self.add_block_to_track(track, time)
    # sync all inputs to the current transport time
    for i in self._active_inputs:
      i.time = 0.0
  # activate a new block on a track to receive recorded events
  def add_block_to_track(self, track, time):
    block = doc.Block(doc.EventList(), time=time, duration=0.5)
    track.append(block)
    self._active_blocks[track] = block
  # receive events
  def on_event(self, from_input, event):
    # get all tracks the input routes to
    to_tracks = self.input_patch_bay.items_connected_from(from_input)
    for track in to_tracks:
      if (track in self._active_blocks):
        # add the event
        block = self._active_blocks[track]
        block.events.append(event)
  # stop recording
  def stop(self):
    # deactivate all blocks
    self._active_blocks = dict()
    
# a controller to manage playback
class Player(observable.Object):
  def __init__(self, transport, output_patch_bay):
    observable.Object.__init__(self)
    self.transport = transport
    self.transport.add_observer(self.on_transport_change)
    self.output_patch_bay = output_patch_bay
    self._playing = False
    # the time events have been scheduled up to (non-inclusive)
    self._scheduled_to = None
    # the amount of time to schedule events into the future
    self.min_schedule_ahead = self.transport.display_interval
    self.max_schedule_ahead = 2.0 * self.min_schedule_ahead
    # a list of tuples containing outputs note-ons have been sent to,
    #  the pitch of the note, and the time at which it should stop playing
    self._open_notes = [ ]
  def on_transport_change(self):
    if (self.transport.playing != self._playing):
      self._playing = self.transport.playing
      if (self._playing):
        self.start()
      else:
        self.stop()
    if (self._playing):
    
      # TODO: handle time jumps
    
      self.send()
  # start playback
  def start(self):
    self._scheduled_to = self.transport.time
    # reset the timers of all output tracks to the transport time
    time = self.transport.time
    for output in self.output_patch_bay.to_items:
      output.connect()
      output.time = time
  # schedule some events for playback
  def send(self):
    # if we're already scheduled ahead enough, we're done
    ahead = self.transport.time - self._scheduled_to
    if (ahead > self.min_schedule_ahead): return
    # get the interval to schedule
    begin = self._scheduled_to
    end = self.transport.time + self.max_schedule_ahead
    # schedule events into the future
    tracks = self.output_patch_bay.from_items
    for track in tracks:
      events = [ ]
      for block in track:
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
      # schedule beginnings og events on all outputs for the track
      for output in self.output_patch_bay.items_connected_from(track):
        for (event, t1) in events:
          t2 = t1
          try:
            t2 += event.duration
          except AttributeError: pass
          velocity = 127
          try:
            velocity = int(math.floor(event.velocity * 127.0))
          except AttributeError: pass
          pitch = None
          try:
            pitch = event.pitch
          except AttributeError: pass
          # start notes
          if (hasattr(event, 'pitch')):
            output.send_message((0x90, pitch, velocity), t1)
            self._open_notes.append((output, pitch, t2))
    # schedule ending events if they are in the current interval
    open_notes = [ ]
    for note in self._open_notes:
      (output, pitch, time) = note
      if ((time >= begin) and (time < end)):
        output.send_message((0x90, pitch, 0), time)
      else:
        open_notes.append(note)
    self._open_notes = open_notes
    self._scheduled_to = end
  # schedule endings for all currently playing notes
  def end_all_notes(self):
    for (output, pitch, time) in self._open_notes:
      output.send_message((0x80, pitch, 0), self._scheduled_to)
    self._open_notes = [ ]
  # stop playback
  def stop(self):
    self.end_all_notes()
    

# a mixer that tracks various properties for a set of tracks
class Mixer(observable.Object):
  def __init__(self, tracks):
    observable.Object.__init__(self)
    # store the "active" track
    self.active_track = None
    # store the track list to control
    self.tracks = tracks
    self.tracks.add_observer(self.on_list_change)
    # assign mixer tracks for the given tracks
    self._pool = dict()
    self.on_list_change()
  # update the list of mixer tracks from the list of tracks
  def on_list_change(self):
    # make sure the active track is always one in the list
    if ((self.active_track is not None) and 
        (self.active_track not in self.tracks)):
      self.active_track = None
    self.on_change()
  # move the active track
  def previous_track(self):
    self.offset_active_track_index(-1)
  def next_track(self):
    self.offset_active_track_index(1)
  def offset_active_track_index(self, offset):
    if (self.active_track is None): return
    try:
      index = self.index(self.active_track)
    except ValueError:
      self.active_track = None
      return
    index = min(max(0, index + offset), len(self) - 1)
    self.active_track = self[index]
  
