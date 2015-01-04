import jackpatch 

from PySide.QtCore import Signal, QTimer

import observable
import serializable
import unit
import midi
from undo import UndoManager

# a transport to keep track of timepoints, playback, and recording
class Transport(observable.Object, unit.Sink):
  # extra signals
  recording_will_start = Signal()
  recording_started = Signal()
  recording_will_stop = Signal()
  recording_stopped = Signal()
  # regular init stuff
  def __init__(self, time=0.0, duration=0.0, cycling=False, marks=()):
    observable.Object.__init__(self)
    unit.Sink.__init__(self)
    # set the interval to update at
    self.update_interval = 0.5
    # get a bridge to the JACK transport
    self._client = jackpatch.Client('jackdaw-transport')
    self._client.activate()
    self._transport = jackpatch.Transport(client=self._client)
    # make a timer to update the transport model when the time changes
    self._update_timer = QTimer(self)
    self._update_timer.setInterval(self.update_interval * 1000)
    self._update_timer.timeout.connect(self.update_timeout)
    # set up internal state
    self._recording = False
    self._cycling = cycling
    # store all time marks
    self.marks = observable.List(marks)
    self._sorting_marks = False
    self.marks.add_observer(self.on_marks_change)
    # the start and end times of the cycle region, which will default
    #  to the next and previous marks if not set externally
    self._cycle_start_time = None
    self.cycle_start_time = None
    self._cycle_end_time = None
    self.cycle_end_time = None
    # store the duration, which is notional and non-constraining, 
    #  and which is meant to be maintained by users of the transport
    self._duration = duration
    # store the time
    self._local_time = None
    self.time = time
    self._last_played_to = time
    self._last_display_update = 0
    self._start_time = None
    self._local_is_rolling = None
    # the amount to change time by when the skip buttons are pressed
    self.skip_delta = 1.0 # seconds
    # make a port and client for transport control
    self._sink_type = 'midi'
    self._sink_port = jackpatch.Port(name='midi.RX', client=self._client,
                                     flags=jackpatch.JackPortIsInput)
    self._input_handler = TransportInputHandler(
      port=self.sink_port, transport=self)
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
      if (value):
        self.recording_will_start.emit()
      else:
        self.recording_will_stop.emit()
      self._recording = value
      if (self._recording):
        self.start()
      else:
        self.pause()
      self.on_change()
      if (value):
        self.recording_started.emit()
      else:
        self.recording_stopped.emit()
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
  @property
  def duration(self):
    return(self._duration)
  @duration.setter
  def duration(self, value):
    if (value != self._duration):
      self._duration = value
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
  def update_timeout(self):
    is_rolling = self.is_rolling
    current_time = self.time
    # clear the locally stored settings because now we're checking 
    #  the real transport
    self._local_is_rolling = None
    self._local_time = None
    self.update(is_rolling=is_rolling, current_time=current_time)
  def update(self, is_rolling=None, current_time=None):
    if (is_rolling is None):
      is_rolling = self.is_rolling
    if (current_time is None):
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
      mark = self.get_previous_mark(current_time + 0.001)
      self._cycle_start_time = mark.time if mark is not None else None
    if (self.cycle_end_time is not None):
      self._cycle_end_time = self.cycle_end_time
    else:
      mark = self.get_next_mark(current_time)
      self._cycle_end_time = mark.time if mark is not None else None
  # jump to the beginning or end
  def go_to_beginning(self):
    self.time = 0.0
  def go_to_end(self):
    self.time = self.duration
  # skip forward or back in time
  def skip_back(self, *args):
    self.time = self.time - self.skip_delta
  def skip_forward(self, *args):
    self.time = self.time + self.skip_delta
  # toggle a mark at the current time
  def toggle_mark(self, *args):
    UndoManager.begin_action(self.marks)
    t = self.time
    found = False
    for mark in set(self.marks):
      if (mark.time == t):
        self.marks.remove(mark)
        found = True
    if (not found):
      self.marks.append(Mark(time=t))
    UndoManager.end_action()
  def on_marks_change(self):
    if (self._sorting_marks): return
    self._sorting_marks = True
    self.marks.sort()
    self.on_change()
    self._sorting_marks = False
  # return the time of the next or previous mark relative to a given time
  def get_previous_mark(self, from_time):
    for mark in reversed(self.marks):
      if (mark.time < from_time):
        return(mark)
    # if we're back past the first mark, treat the beginning 
    #  like a virtual mark
    return(Mark(time=0.0))
  def get_next_mark(self, from_time):
    for mark in self.marks:
      if (mark.time > from_time):
        return(mark)
    return(None)
  # move to the next or previous mark
  def previous_mark(self, *args):
    mark = self.get_previous_mark(self.time)
    if (mark is not None):
      self.time = mark.time
  def next_mark(self, *args):
    mark = self.get_next_mark(self.time)
    if (mark is not None):
      self.time = mark.time
  # transport serialization
  def serialize(self):
    return({
      'time': self.time,
      'duration': self.duration,
      'cycling': self.cycling,
      'marks': list(self.marks)
    })
serializable.add(Transport)

# a model to store a marked timepoint on a transport
class Mark(observable.Object):
  def __init__(self, time=0.0):
    observable.Object.__init__(self)
    self._time = time
  @property
  def time(self):
    return(self._time)
  @time.setter
  def time(self, value):
    if (value != self._time):
      self._time = value
      self.on_change()
  # overload the less-than operator for sorting by time
  def __lt__(self, other):
    return(self.time < other.time)
  def serialize(self):
    return({
      'time': self.time
    })
serializable.add(Mark)

# a handler for MIDI commands that control the transport
class TransportInputHandler(midi.InputHandler):
  def __init__(self, port, transport):
    midi.InputHandler.__init__(self, port=port, target=transport)
    self._leds = dict()
    self._hold_button = None
    self._hold_timer = None
    # a port to send messages back to transport controllers
    self._send_port = None
    # the names of controller clients that have been connected 
    #  to the transport
    self._connected_controllers = set()
    self.transport.add_observer(self.on_transport_change)
    self.on_transport_change()
  @property
  def transport(self):
    return(self._target)
  # connect back to all controlling devices
  def on_transport_change(self):
    # update connections to controlling devices
    ports = self.port.get_connections()
    for port in ports:
      name = port.name.split(':')[0]
      if (name in self._connected_controllers): continue
      self.connect_controller(name)
    # update LED state on controlling devices
    if (self.transport):
      self.update_led(self.PLAY_BUTTON, self.transport.playing)
      self.update_led(self.RECORD_BUTTON, self.transport.recording)
      self.update_led(self.CYCLE_BUTTON, self.transport.cycling)
#    if (self.mixer):
#      for track_index in range(0, 8):
#        if (track_index < len(self.mixer.tracks)):
#          track = self.mixer.tracks[track_index]
#          self.update_led(self.SOLO | track_index, track.solo)
#          self.update_led(self.MUTE | track_index, track.mute)
#          self.update_led(self.ARM | track_index, track.arm)
#        else:
#          self.update_led(self.SOLO | track_index, False)
#          self.update_led(self.MUTE | track_index, False)
#          self.update_led(self.ARM | track_index, False)
  def connect_controller(self, name):
    # get an input port for the device
    input_ports = self.port.client.get_ports(name_pattern=name+':.*',
                                             type_pattern='.*midi.*',
                                            flags=jackpatch.JackPortIsInput)
    if (len(input_ports) == 0): return
    input_port = input_ports[0]
    if (self._send_port is None):
      self._send_port = jackpatch.Port(client=self.port.client,
                                       name="midi.TX", 
                                       flags=jackpatch.JackPortIsOutput)
    self.port.client.connect(self._send_port, input_port)
    self._connected_controllers.add(name)
    self.init_controllers()
  def init_controllers(self):
   # send a sysex message to let the controller know we'll be
   #  managing the state of its LEDs
   self.send_message([ 0xF0, 0x42, 0x40, 0x00, 0x01, 0x13,
                       0x00, 0x00, 0x00, 0x01, 0xF7 ])
   # turn off all LEDs initially
   for i in range(0, 128):
     self.update_led(i, False)
  # send a message back to the controlling device
  def send_message(self, data):
    if (self._send_port is None): return
    self._send_port.send(data, 0.0)
  # controller button values
  PLAY_BUTTON = 0x29
  STOP_BUTTON = 0x2A
  BACK_BUTTON = 0x2B
  FORWARD_BUTTON = 0x2C
  RECORD_BUTTON = 0x2D
  CYCLE_BUTTON = 0x2E
  PREVIOUS_TRACK_BUTTON = 0x3A
  NEXT_TRACK_BUTTON = 0x3B
  SET_MARK_BUTTON = 0x3C
  PREVIOUS_MARK_BUTTON = 0x3D
  NEXT_MARK_BUTTON = 0x3E
  # controller type masks
  TRANSPORT = 0x28
  MARK = 0x38
  LEVEL = 0x00
  PAN = 0x10
  SOLO = 0x20
  MUTE = 0x30
  ARM = 0x40
  PER_TRACK = (LEVEL, PAN, SOLO, MUTE, ARM)
  # interpret messages
  def handle_message(self, data, time):
    # ignore all long messages
    if (len(data) != 3): return
    (status, controller, value) = data
    # filter for control-change messages
    if ((status & 0xF0) != 0xB0): return
    # get the kind of control this is
    kind = (controller & 0xF8)
    # handle mode buttons
    if (controller == self.PLAY_BUTTON):
      if ((value > 64) and (self.transport)):
        self.transport.play()
    elif (controller == self.RECORD_BUTTON):
      if ((value > 64) and (self.transport)):
        self.transport.record()
    elif (controller == self.CYCLE_BUTTON):
      if ((value > 64) and (self.transport)):
        self.transport.cycling = not self.transport.cycling
    # handle action buttons
    elif ((kind == self.TRANSPORT) or (kind == self.MARK)):
      if (value > 64):
        if (self.transport):
          if (controller == self.STOP_BUTTON):
            self.transport.stop()
          elif (controller == self.BACK_BUTTON):
            self.transport.skip_back()
            self.set_holding(controller)
          elif (controller == self.FORWARD_BUTTON):
            self.transport.skip_forward()
            self.set_holding(controller)
          elif (controller == self.PREVIOUS_MARK_BUTTON):
            self.transport.previous_mark()
            self.set_holding(controller)
          elif (controller == self.NEXT_MARK_BUTTON):
            self.transport.next_mark()
            self.set_holding(controller)
          elif (controller == self.SET_MARK_BUTTON):
            self.transport.toggle_mark()
            self.set_holding(controller)
        #if (self.mixer):
          #if (controller == self.PREVIOUS_TRACK_BUTTON):
            #self.mixer.previous_track()
          #elif (controller == self.NEXT_TRACK_BUTTON):
            #self.mixer.next_track()
      else:
        self.clear_holding()
      self.update_led(controller, value > 64)
    #elif (kind in self.PER_TRACK):
      #track_index = controller & 0x07
      #if ((self.mixer) and (track_index < len(self.mixer.tracks))):
        #track = self.mixer.tracks[track_index]
        #if (kind == self.LEVEL):
          #track.level = float(value) / 127
        #elif (kind == self.PAN):
          #track.pan = ((float(value) / 127) * 2) - 1.0
        #if (value > 64):
          #if (kind == self.SOLO):
            #track.solo = not track.solo
          #elif (kind == self.MUTE):
            #track.mute = not track.mute
          #elif (kind == self.ARM):
            #track.arm = not track.arm
    else:
      print('Unhandled message type %02X' % (controller))
  # handle a button being held down
  def set_holding(self, button):
    self._hold_button = button
    if (self._hold_timer is None):
      self._hold_timer = QTimer(self)
      self._hold_timer.timeout.connect(self.on_hold)
    self._hold_timer.setInterval(500)
    self._hold_timer.start()
  def clear_holding(self):
    self._hold_button = None
    if (self._hold_timer is not None):
      self._hold_timer.stop()
  def on_hold(self):
    if (self._hold_button is None):
      try:
        self._hold_timer.stop()
      except AttributeError: pass
      return
    self.handle_message([ 0xBF, self._hold_button, 127 ], 0.0)
    if ((self._hold_timer is not None) and 
        (self._hold_timer.interval() != 100)):
      self._hold_timer.setInterval(100)
  # send a message to update the state of a button LED
  def update_led(self, button, on):
    try:
      old_value = self._leds[button]
    except KeyError:
      old_value = None
    value = 0
    if (on):
      value = 127
    if (value != old_value):
      self._leds[button] = value
      self.send_message([ 0xBF, button, value ])

# make a unit that represents a transport
class TransportUnit(unit.Unit):
  def __init__(self, transport, *args, **kwargs):
    unit.Unit.__init__(self, *args, **kwargs)
    self.transport = transport
    self.transport.add_observer(self.on_change)
  def serialize(self):
    obj = unit.Unit.serialize(self)
    obj['transport'] = self.transport
    return(obj)
serializable.add(TransportUnit)