import time

from gi.repository import GLib

import observable

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
        self.run()
      else:
        self.stop()
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
        self.run()
      else:
        self.stop()
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
  def run(self):
    self._start_time = time.time()
    self._last_played_to = self._time
    # establish the cycle region
    self.update_cycle_bounds()
    # start the update timer
    if (self._run_timer is None):
      self._run_timer = GLib.idle_add(self.on_running)
  # stop the time moving forward
  def stop(self):
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
  def skip_back(self):
    self.time = self.time - self.skip_delta
  def skip_forward(self):
    self.time = self.time + self.skip_delta
  # toggle a mark at the current time
  def toggle_mark(self):
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
  def previous_mark(self):
    t = self.get_previous_mark(self.time)
    if (t is not None):
      self.time = t
  def next_mark(self):
    t = self.get_next_mark(self.time)
    if (t is not None):
      self.time = t
      
# a mixer that tracks various properties for a set of tracks
class Mixer(observable.List):
  def __init__(self, tracks):
    observable.List.__init__(self)
    # store the "active" track
    self.active_track = None
    # store the track list to control
    self.tracks = tracks
    self.tracks.add_listener(self.on_list_change)
    # assign mixer tracks for the given tracks
    self._pool = dict()
    self.on_list_change()
  # update the list of mixer tracks from the list of tracks
  def on_list_change(self):
    old_pool = self._pool
    new_pool = dict()
    new_list = [ ]
    for track in self.tracks:
      if (track in old_pool):
        item = old_pool[track]
      else:
        item = MixerTrack(track)
      new_pool[track] = item
      new_list.append(item)
    self._pool = new_pool
    self[0:] = new_list    
  # make sure the active track is always one in the list
  def on_change(self):
    if ((self.active_track is not None) and 
        (self.active_track not in self)):
      self.active_track = None
    # transfer global track state to the tracks
    self.tracks.remove_listener(self.on_list_change)
    solos = [ ]
    for item in self:
      if (item.solo):
        solos.append(item)
    if (len(solos) > 0):
      for item in self:
        item.track.enabled = (item in solos)
    else:
      for item in self:
        item.track.enabled = not item.mute
    for item in self:
      item.track.armed = item.arm
    self.tracks.add_listener(self.on_list_change)
    observable.List.on_change(self)
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
  
  
  
# a track descriptor on a mixer
class MixerTrack(observable.Object):
  def __init__(self, track):
    observable.Object.__init__(self)
    # store the track this controls
    self.track = track
    # initialize state
    self._solo = False
    self._mute = False
    self._arm = False
    self._level = 1.0
    self._pan = 0.0
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
