import jackpatch 

from PySide.QtCore import Signal, QTimer

import observable
import serializable

# a transport to keep track of timepoints, playback, and recording
class Transport(observable.Object):
  # regular init stuff
  def __init__(self, time=0.0, cycling=False, marks=None):
    observable.Object.__init__(self)
    # set the interval to update at
    self.update_interval = 0.5
    # get a bridge to the JACK transport
    self._client = jackpatch.Client('jackdaw-transport')
    self._transport = jackpatch.Transport(client=self._client)
    # make a timer to update the transport model when the time changes
    self._update_timer = QTimer(self)
    self._update_timer.setInterval(self.update_interval * 1000)
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