import time
import re

from gi.repository import GLib, GObject

from ..common import observable, serializable
import core
from ..models import doc

# handle MIDI input events when the UI is idling
_input_adapters = set()
def _service_input_adapters():
  global _input_adapters
  for adapter in _input_adapters:
    if (adapter.device):
      if (adapter.device.is_connected):
        while (True):
          result = adapter.device.receive()
          if (result is None): break
          adapter.receive_message(result[0], result[1])
      else:
        adapter.is_plugged = False
  return(True)
GObject.idle_add(_service_input_adapters)

# acts as a base class for MIDI input device adapters
class InputAdapter(core.DeviceAdapter):
  def __init__(self, device):
    core.DeviceAdapter.__init__(self, device)
    # keep a list of methods to call when events become available
    self._listeners = set()
  # register/unregister the input for polling
  def on_connect(self):
    _input_adapters.add(self)
    self._base_time = self.device.get_time()
  def on_disconnect(self):
    if (self in _input_adapters):
      _input_adapters.remove(self)
  # determine whether input is available from the named device
  def is_available(self):
    return((self.is_plugged) and 
           (self.is_input_available))
  # add and remove listeners to receive generated doc.Event instances
  def add_listener(self, listener):
    self._listeners.add(listener)
  def remove_listener(self, listener):
    try:
      self._listeners.remove(listener)
    except KeyError: pass
  # send a new doc.Event to all listeners
  def send_event(self, event):
    for listener in self._listeners:
      listener(self, event)
  # handle messages from the device
  def receive_message(self, message, message_time):
    self.on_message(message_time - self._base_time, message)
  # receive an message from the input port, override to handle
  def on_message(self, time, message):
    pass
  # send a message to the output port if possible
  def send_message(self, message):
    if ((self.device) and (self.device.is_output)):
      self.device.send(message)
serializable.add(InputAdapter)

# a list of all available input devices
class InputList(core.DeviceAdapterList):
  def __init__(self, devices=()):
    core.DeviceAdapterList.__init__(self, adapter_class=NoteInput)
  def include_device(self, device):
    if (not device): return(False)
    if (device.name in ('Timer', 'Announce', 'Notify')): return(False)
    if (device.name.startswith('Midi Through')): return(False)
    return(device.is_input)
    
# interprets note and control channel messages
class NoteInput(InputAdapter):
  def __init__(self, device):
    InputAdapter.__init__(self, device)
    # hold a set of notes for all "voices" currently playing, keyed by pitch
    self._playing_notes = dict()
  @property
  def playing_notes(self):
    return(self._playing_notes.values())
  def end_all_notes(self):
    self._playing_notes = dict()
  # interpret messages
  def on_message(self, time, message):
    status = message[0]
    data1 = message[1]
    data2 = message[2]
    kind = (status & 0xF0) >> 4
    channel = (status & 0x0F)
    # get note on/off messages
    if ((kind == 0x08) or (kind == 0x09)):
      pitch = data1
      velocity = data2 / 127.0
      # note on
      if (kind == 0x09):
        note = doc.Note(time=time, pitch=pitch, velocity=velocity, duration=0)
        self._playing_notes[pitch] = note
        self.send_event(note)
      # note off
      elif (kind == 0x08):
        try:
          note = self._playing_notes[pitch]
        # this indicates a note-off with no prior note-on, not a big deal
        except KeyError: return
        note.duration = time - note.time
        del self._playing_notes[pitch]
    # report unexpected messages
    else:
      print('%s: Unhandled message type %02X' % (self.name, status))
serializable.add(NoteInput)

# handles input/output for a Korg NanoKONTROL2
class NanoKONTROL2(InputAdapter):
  def __init__(self, transport=None, mixer=None):
    InputAdapter.__init__(self, None)
    # cache state for all the leds to reduce update message overhead
    self._leds = dict()
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
    # set up to autoconnect if the device is plugged in
    core.DevicePool.add_observer(self.on_pool_change)
    self.on_pool_change()
  # when a matching device is plugged in, connect to it
  def on_pool_change(self):
    for device in core.DevicePool.plugged:
      if (device is self.device):
        if (not self.is_connected):
          self.connect()
        self.is_plugged = True
        return
      elif (device.name.startswith('nanoKONTROL2')):
        self.disconnect()
        self.device = device
        self.connect()
        self.is_plugged = True
        return
    self.is_plugged = False
  # do setup on connection with the device
  def on_connect(self):
    InputAdapter.on_connect(self)
    # send a sysex message to let the controller know we'll be
    #  managing the state of its LEDs
    self.send_message([ 0xF0, 0x42, 0x40, 0x00, 0x01, 0x13,
                        0x00, 0x00, 0x00, 0x01, 0xF7 ])
    # turn off all LEDs initially
    for i in range(0, 128):
      self.update_led(i, False)
  
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
    # ignore all long messages
    if (len(message) != 3): return
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
            track.arm = not track.arm
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

