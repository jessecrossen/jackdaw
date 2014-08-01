import time
import rtmidi

from gi.repository import GLib, GObject

import observable

# handle MIDI input events when the UI is idling
_devices = set()
def _service_devices():
  for device in _devices:
    while(True):
      result = device._in.get_message()
      if (result is None): break
      device.receive_message(result[0], result[1])
  return(True)
GObject.idle_add(_service_devices)

# acts as a base class for MIDI input device adapters
class Device(object):
  def __init__(self):
    self._in = rtmidi.MidiIn()
    self._out = rtmidi.MidiOut()
    self._last_message_time = None
    self._abs_time = time.time()
  # connect to the first device with the given name or name fragment
  def connect_by_name(self, name):
    in_port = self.get_port_by_name(self._in, name)
    out_port = self.get_port_by_name(self._out, name)
    if (in_port is not None):
      self._in.open_port(in_port)
      _devices.add(self)
    else:
      print('Failed to connect input for the device named %s.' % (name))
    if (out_port is not None):
      self._out.open_port(out_port)
    else:
      print('Failed to connect output for the device named %s.' % (name))
  # disconnect from inputs and outputs
  def disconnect(self):
    if (self in _devices):
      _devices.remove(self)
    del self._in
    del self._out
    self._in = rtmidi.MidiIn()
    self._out = rtmidi.MidiOut()
  # get the port on the given input/output with the given name
  def get_port_by_name(self, connection, name):
    port_count = connection.get_port_count()
    for port in range(0, port_count):
      device_name = connection.get_port_name(port).lower()
      if (name in device_name):
        return(port)
    return(None)
  # handle messages from the device
  def receive_message(self, message, delta_time):
    # accumulate time deltas to provide total time
    now = time.time()
    if (self._last_message_time is None):
      message_time = now - self._abs_time
      self._last_message_time = message_time
    else:
      self._last_message_time += delta_time
      message_time = self._last_message_time
    self._abs_time = now
    self.on_message(message_time, message)
  # receive an message from the input port, override to handle
  def on_message(self, time, message):
    pass
  # send a message to the output port if possible
  def send_message(self, message):
    self._out.send_message(message)
  # get the amount of time elapsed since the time origin
  @property
  def time(self):
    elapsed = time.time() - self._abs_time
    return(self._last_message_time + elapsed)
  # reset the time origin to the given value, such that subsequent
  #  messages have a time relative to it
  @time.setter
  def time(self, value):
    self._last_message_time = None
    self._abs_time = time.time() - value

# handles input/output for a Korg NanoKONTROL2
class NanoKONTROL2(Device):
  def __init__(self, transport=None, mixer=None):
    Device.__init__(self)
    self.connect_by_name('nanokontrol2')
    # cache state for all the leds to reduce update message overhead
    self._leds = dict()
    # send a sysex message to let the controller know we'll be
    #  managing the state of its LEDs
    self.send_message([ 0xF0, 0x42, 0x40, 0x00, 0x01, 0x13,
                        0x00, 0x00, 0x00, 0x01, 0xF7 ])
    # turn off all LEDs initially
    for i in range(0, 128):
      self.update_led(i, False)
    # store the controlled objects
    self.transport = transport
    if (self.transport):
      self.transport.add_observer(self.on_change)
    self.mixer = mixer
    if (self.mixer):
      self.mixer.add_observer(self.on_change)
    # set up timers for detecting button holds
    self._hold_timer = None
    self._repeat_timer = None
    self._hold_button = None
  
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
  
  # update the device to reflect changes to the transport/mixer state
  def on_change(self):
    if (self.transport):
      self.update_led(self.PLAY_BUTTON, self.transport.playing)
      self.update_led(self.RECORD_BUTTON, self.transport.recording)
      self.update_led(self.CYCLE_BUTTON, self.transport.cycling)
    if (self.mixer):
      for track_index in range(0, 8):
        if (track_index < len(self.mixer.tracks)):
          track = self.mixer.tracks[track_index]
          self.update_led(self.SOLO | track_index, track.solo)
          self.update_led(self.MUTE | track_index, track.mute)
          self.update_led(self.ARM | track_index, track.arm)
        else:
          self.update_led(self.SOLO | track_index, False)
          self.update_led(self.MUTE | track_index, False)
          self.update_led(self.ARM | track_index, False)
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
  
  # interpret messages
  def on_message(self, time, message):
    (status, controller, value) = message
    # filter for control-change messages
    if ((status & 0xF0) != 0xB0): return
    # get the kind of control this is
    kind = (controller & 0xF8)
    # handle mode buttons
    if (controller == self.PLAY_BUTTON):
      if ((value > 64) and (self.transport)):
        self.transport.play()
    elif (controller == self.RECORD_BUTTON):
      if ((value > 64) and (self.transport) and (self.mixer)):
        track_armed = False
        for track in self.mixer.tracks:
          if (track.arm):
            self.transport.record()
            break
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
        if (self.mixer):
          if (controller == self.PREVIOUS_TRACK_BUTTON):
            self.mixer.previous_track()
          elif (controller == self.NEXT_TRACK_BUTTON):
            self.mixer.next_track()
      else:
        self.clear_holding()
      self.update_led(controller, value > 64)
    elif (kind in self.PER_TRACK):
      track_index = controller & 0x07
      if ((self.mixer) and (track_index < len(self.mixer.tracks))):
        track = self.mixer.tracks[track_index]
        if (kind == self.LEVEL):
          track.level = float(value) / 127
        elif (kind == self.PAN):
          track.pan = ((float(value) / 127) * 2) - 1.0
        if (value > 64):
          if (kind == self.SOLO):
            track.solo = not track.solo
          elif (kind == self.MUTE):
            track.mute = not track.mute
          elif (kind == self.ARM):
            if (track.arm):
              track.arm = False
            else:
              for arm_track in self.mixer.tracks:
                arm_track.arm = (arm_track is track)
    else:
      print('NanoKONTROL2: Unhandled message type %02X' % (controller))
  # handle a button being held down
  def set_holding(self, button):
    if (self._hold_timer is None):
      self._hold_button = button
      self._hold_timer = GLib.timeout_add(500, self.on_hold)
  def clear_holding(self):
    self._hold_button = None
    if (self._hold_timer is not None):
      GLib.source_remove(self._hold_timer)
      self._hold_timer = None
    if (self._repeat_timer is not None):
      GLib.source_remove(self._repeat_timer)
      self._repeat_timer = None
  def on_hold(self):
    if (self._hold_button is None): return(False)
    self.on_message(self.time, [ 0xBF, self._hold_button, 127 ])
    if (self._repeat_timer is None):
      self._repeat_timer = GLib.timeout_add(100, self.on_hold)
      return(False)
    return(True)

