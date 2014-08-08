import time

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
      t += time.time() - self._start_time
    return(t)
  @time.setter
  def time(self, t):
    self._time = max(0.0, t)
    if (self._start_time is not None):
      self._start_time = time.time()
    self.update_cycle_bounds()
    self.on_change()
  
  # start the time moving forward
  def _run(self):
    self._start_time = time.time()
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
    abs_time = time.time()
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
  def __init__(self, transport, patch_bay):
    observable.Object.__init__(self)
    self.transport = transport
    self.transport.add_observer(self.on_transport_change)
    self.patch_bay = patch_bay
    self.patch_bay.add_observer(self.on_patch_bay_change)
    # track whether we've registered the start of recording
    self._recording = False
    # hold a list of tracks mapped to the block on that track that's 
    #  receiving input
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
  def on_patch_bay_change(self):
    pass
  # start recording
  def start(self):
    # get the current transport time so it's the same across tracks
    time = self.transport.time
    # find all armed tracks with input connections
    tracks = self.patch_bay.to_items
    for track in tracks:
      if (track.arm):
        self._active_tracks.add(track)
        incoming_inputs = self.patch_bay.items_connected_to(track)
        self._active_inputs.update(incoming_inputs)
    # add a block with an event list to each one, starting at 
    #  the transport's current time
    for track in self._active_tracks:
      self.add_block_to_track(track, time)
    # connect to inputs
    for active_input in self._active_inputs:
      # reset all inputs to zero time
      active_input.time = 0.0
      # make sure all active inputs are connected
      if (not active_input.is_connected):
        active_input.connect()
      # listen for events from all active inputs
      active_input.add_listener(self.on_event)
  # activate a new block on a track to receive recorded events
  def add_block_to_track(self, track, time):
    block = doc.Block(doc.EventList(), time=time, duration=0.5)
    track.append(block)
    self._active_blocks[track] = block
  # receive events
  def on_event(self, from_input, event):
    # get all tracks the input routes to
    to_tracks = self.patch_bay.items_connected_from(from_input)
    for track in to_tracks:
      if (track in self._active_blocks):
        # add the event
        block = self._active_blocks[track]
        block.events.append(event)
  # stop recording
  def stop(self):
    # stop listening to inputs
    for active_input in self._active_inputs:
      active_input.remove_listener(self.on_event)
    # reset all connections
    self._active_inputs = set()
    self._active_tracks = set()
    self._active_blocks = dict()

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
  
