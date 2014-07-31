import pygame.midi

pygame.midi.init()

# this class exposes an incoming stream of MIDI messages
class MidiReceiver():
  def __init__(self):    
    self.devices = [ ]
    for device_id in range(0, pygame.midi.get_count()):
      result = pygame.midi.get_device_info(device_id)
      if (result == None): break
      (interf, name, is_input, is_output, is_opened) = result
      if (is_input != 0):
        self.devices.append((name, pygame.midi.Input(device_id, 64)))
    self.listeners = set()
  
  # add a listener whose 'on_midi' event will be called
  #  whenever a MIDI event is received
  def addListener(self, obj):
    self.listeners.add(obj)
  
  # receive midi events and route them to listeners
  # this should be called at lease every frame
  def update(self):
    for (name, device) in self.devices:
      while (device.poll()):
        event = device.read(1)
        for listener in self.listeners:
          listener.on_midi(name, event[0])

