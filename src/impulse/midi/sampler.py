import os
import sys
import time
import re
import subprocess
import fcntl
import atexit
import socket

from gi.repository import GLib

import outputs
from ..common import observable

# escape string literals for inclusion in LSCP commands
def _escape(s):
  m = { '\'': '\\\'', '"': '\\"', '\\': '\\\\',
        '\n': '\\n', '\r': '\\r', '\f': '\\f', '\t': '\\t', '\v': '\\v' }
  out = ''
  for c in s:
    if (c in m):
      out += m[c]
    elif (ord(c) > 127):
      out += ('%2X' % ord(c))
    else:
      out += c
  return(out)

# manage a sampler-based instrument
class Instrument(observable.Object):
  def __init__(self, sampler, port=0, path=None):
    observable.Object.__init__(self)
    self._sampler = sampler
    self._path = None
    self._channel = None
    self._port = port
    self._progress = 0
    self._progress_timer = None
    self._engine = None
    self.path = path
  @property
  def channel(self):
    return(self._channel)
  @property
  def path(self):
    return(self._path)
  @path.setter
  def path(self, value):
    if (value != self._path):
      self._path = value
      self._attach()
  # add a sampler channel for the instrument and load a sample file, if any
  def _attach(self):
    # if we already have a channel, we can go straight to loading an instrument
    if (self._channel is not None):
      self._load_engine()
    # otherwise request a new channel from the sampler
    else:
      self._sampler.call('ADD CHANNEL', self._on_channel_add)
  def _on_channel_add(self, result):
    m = re.match('OK\[(.*)\]', result)
    if (m):
      self._channel = int(m.group(1))
      self._set_io()
  # connect an input/output devices for the channel
  def _set_io(self):
    self._sampler.call(
      'SET CHANNEL AUDIO_OUTPUT_DEVICE %d %d' % 
        (self.channel, self._sampler.output_id), 
          self._on_output_set)
  def _on_output_set(self, result):
    if (result.startswith('OK')):
      self._sampler.call(
        'ADD CHANNEL MIDI_INPUT %d %d %d' % 
          (self.channel, self._sampler.device_id, self._port), 
            self._on_input_set)
  def _on_input_set(self, result):
    if (result.startswith('OK')):
      self._sampler.call(
        'SET CHANNEL MIDI_INPUT_CHANNEL %d %d' %
          (self._channel, self._channel), self._on_midi_channel_set)
  def _on_midi_channel_set(self, result):
    if (result.startswith('OK')):
      self._load_engine()
  # load a sampler engine for the channel
  def _load_engine(self):
    if (self._path is None): return
    m = re.search('\.([^.]+)$', self._path)
    if (not m):
      self._sampler._warn(
        'Unable to find a sampler engine for "%s"' % self._path)
    ext = m.group(1).upper()
    if (ext in self._sampler.engines):
      if (ext != self._engine):
        self._engine = ext
        self._sampler.call('LOAD ENGINE %s %d' % 
          (self._engine, self._channel), self._on_engine_load)
    else:
      self._sampler._warn(
        'Engine "%s" is not one of the available engines ("%s")' % 
          (ext, '","'.join(self._sampler.engines)))
  def _on_engine_load(self, result):
    if (result == 'OK'):
      self._load_path()
  # load a new instrument
  def _load_path(self):
    if (self._path is None): return
    # stop the progress timer if an instrument was being loaded
    if (self._progress_timer is not None):
      GLib.source_remove(self._progress_timer)
      self._progress_timer = None
    # reset the progress
    self._progress = 0
    # start loading the instrument from the current path
    self._sampler.call('LOAD INSTRUMENT NON_MODAL "%s" 0 %d' %
      (_escape(self._path), self.channel), self._on_load_start)
  # handle the instrument beginning to load
  def _on_load_start(self, result):
    if (result.startswith('OK')):
      self._progress_timer = GLib.timeout_add(500, self._update_progress)
  # check for progress in loading the instrument
  def _update_progress(self):
    if ((self._progress >= 100) or (self._progress < 0)):
      self._progress_timer = None
      return(False)
    self._sampler.call('GET CHANNEL INFO %d' % self.channel, 
      self._on_progress)
  def _on_progress(self, info):
    if ((info) and ('INSTRUMENT_STATUS' in info)):
      self._progress = info['INSTRUMENT_STATUS']  

# manage a LinuxSampler process acting as a backend for sample playback
class LinuxSamplerSingleton(observable.Object):
  def __init__(self, 
      preferred_outputs=('ALSA', 'JACK', 'OSS'),
      preferred_inputs=('ALSA', 'JACK', 'OSS')):
    observable.Object.__init__(self)
    self.verbose = True
    self.address = '0.0.0.0'
    self.port = '8888'
    self.device_id = None
    self.preferred_inputs = preferred_inputs
    self.preferred_outputs = preferred_outputs
    self._reset()
  # log activity
  def _log(self, message):
    if (self.verbose):
      print(message)
  def _warn(self, message):
    sys.stderr.write('WARNING: LinuxSampler: '+message+'\n')
  # reset state
  def _reset(self):
    # the subprocess the sampler is running in
    self.process = None
    self._stderr = ''
    self._stdout = ''
    # status flags about the sampler
    self.started = False
    self.ready = False
    self.input_connected = False
    self.output_connected = False
    self.output_id = 0
    # a socket for communicating with the sampler
    self.connection = None
    self._received = ''
    # queued calls to the sampler
    self._pending_call = None
    self._queued_calls = list()
    # info about the server
    self.server_info = dict()
    self.engines = list()
    # active timeouts
    self.status_timeout = None
    self._receive_timeout = None
    # a list for instrument managers, each one handling a channel
    self._instruments = list()
    # when started, check the status of the connection by asking for info
    self.call('GET SERVER INFO', self._on_server_info)
    # see what engines are available
    self.call('LIST AVAILABLE_ENGINES', self._on_engines)
  # start the LinuxSampler backend
  def start(self):
    if (self.process is not None): return
    self._log('starting sampler')
    self.process = subprocess.Popen(('linuxsampler', 
      '--lscp-addr='+self.address, '--lscp-port='+self.port), -1,
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def set_nonblocking(stream):
      flags = fcntl.fcntl(stream, fcntl.F_GETFL)
      fcntl.fcntl(stream, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    set_nonblocking(self.process.stdout)
    set_nonblocking(self.process.stderr)
    atexit.register(self.stop)
    self.status_timeout = GLib.timeout_add(1000, self._check_status)
  # stop running the service
  def stop(self):
    if (not self.process): return
    # stop timeouts
    if (self.status_timeout):
      GLib.source_remove(self.status_timeout)
    elif (self._receive_timeout):
      GLib.source_remove(self._receive_timeout)
    if (self.connection):
      self._log('closing connection')
      try:
        self.connection.shutdown(1)
        self.connection.close()
      except socket.error:
        pass
    self._log('terminating sampler')
    self.process.terminate()
    time.sleep(0.25)
    tries = 4
    while ((tries >= 0) and (self.process.poll() is None)):
      time.sleep(0.5)
      self._log('killing sampler, %d attempts remaining' % tries)
      self.process.kill()
      tries -= 1
    self._reset()
    self.on_change()
  # get output from the process
  def _check_status(self):
    # if the process dies, stop checking its status
    if (self.process.poll()):
      self.process = None
      self.status_timeout = None
      return(False)
    try:
      self._stdout += self.process.stdout.read()
    except IOError:
      pass
    try:
      self._stderr += self.process.stderr.read()
    except IOError:
      pass
    errors = self._stderr.split('\n')
    if (len(errors) > 1):
      self._stderr = errors[-1]
      errors = errors[0:-1]
      for error in errors:
        self._on_error(error)
    lines = self._stdout.split('\n')
    if (len(lines) > 1):
      self._stdout = lines[-1]
      lines = lines[0:-1]
      for line in lines:
        self._on_line(line)
    return(True)
  # respond to output lines and errors
  def _on_line(self, line):
    # check for the sampler being started
    m = re.match('Starting LSCP network server.*[.]{3}(.*)$', line)
    if (m):
      result = m.group(1)
      if (result == 'OK'):
        self._log('sampler started')
        self.started = True
        self.on_change()
        self._on_start()
  def _on_error(self, error):
    self._warn(error)
  # respond to the sampler being started
  def _on_start(self):
    self.connection = socket.create_connection((self.address, self.port))
    self.connection.setblocking(0)
    self._next_call()
  # send a command to the sampler
  def call(self, command, callback=None):
    # queue calls if the connection isn't open or one is pending
    if ((self._pending_call) or not (self.connection)):
      self._queued_calls.append((command, callback))
      return
    # make a call
    self._log('making call: '+command)
    self._pending_call = (command, callback)
    command = command+'\r\n'
    while (len(command) > 0):
      bytes = self.connection.send(command)
      command = command[bytes:]
    # listen for the response
    self._receive_timeout = GLib.timeout_add(100, self._receive)
  def _next_call(self):
    # send the next call in the queue if there is one
    if (len(self._queued_calls) > 0):
      params = self._queued_calls[0]
      self._queued_calls = self._queued_calls[1:]
      self.call(*params)
      return(True)
    else:
      return(False)
  # receive a response from the sampler
  def _receive(self):
    try:
      self._received += self.connection.recv(1024)
    except IOError:
      return(True)
    # only consider the request finished if we have a complete line
    if ((len(self._received) < 2) or (self._received[-2:] != '\r\n')):
      return(True)
    # break into lines
    lines = self._received[0:-2].split('\r\n')
    # if we got a single line, the request is complete
    result = None
    if (len(lines) == 1):
      line = lines[0]
      # detect errors
      if ((line.startswith('WRN')) or (line.startswith('ERR'))):
        self._warn(line)
      # handle list-like responses
      command = self._pending_call[0]
      if (command.startswith('LIST')):
        result = line.split(',')
        for i in range(0, len(result)):
          result[i] = result[i].strip('\'"')
      else:
        result = line
    # if multiline, wait for a final line with just a period
    elif ((len(lines) > 1) and (lines[-1] == '.')):
      result = dict()
      for line in lines[0:-1]:
        m = re.match('^(\\w+):\\s*(.*)$', line)
        if (m):
          result[m.group(1)] = m.group(2)
    else:
      return(True)
    self._received = ''
    # show the result
    self._log('server responded: '+repr(result))
    # trigger the callback
    callback = self._pending_call[1]
    if (callback is not None):
      callback(result)
    self._pending_call = None
    # send the next call in the queue if there is one
    if (not self._next_call()):
      self._receive_timeout = None
    return(False)
  # respond to getting the first info from the server
  def _on_server_info(self, info):
    self.server_info.update(info)
    # once we get this, we should be ready to rock and roll
    self._log('sampler is ready')
    self.ready = True
    self.on_change()
    # connect automatically for input and output
    self._connect_output()
    self._connect_input()
  def _on_engines(self, engines):
    self.engines = engines
  # set up audio output
  def _connect_output(self):
    def on_connected(result):
      if (result.startswith('OK') or (result.startswith('WRN'))):
        m = re.match('OK\[(.*)\]', result)
        if (m):
          self.output_id = int(m.group(1))
        self.output_connected = True
        self.on_change()
      else:
        self._warn('failed to connect audio output: %s' % result)
    def on_drivers(drivers):
      if (not (len(drivers) > 0)):
        self._warn('No audio output drivers available.')
        return
      selected = drivers[0]
      for driver in self.preferred_outputs:
        if (driver in drivers):
          selected = driver
          break
      self.call('CREATE AUDIO_OUTPUT_DEVICE %s' % selected, on_connected)
    self.call('LIST AVAILABLE_AUDIO_OUTPUT_DRIVERS', on_drivers)
  # set up midi input
  def _connect_input(self):
    def on_connected(result):
      if (result.startswith('OK') or (result.startswith('WRN'))):
        m = re.match('OK\[(.*)\]', result)
        if (m):
          self.device_id = int(m.group(1))
          # rename the port, without a callback because this is optional
          self.call(
            'SET MIDI_INPUT_PORT_PARAMETER %s 0 NAME="LinuxSampler 0"' %
              self.device_id)
        self.input_connected = True
        self.on_change()
      else:
        self._warn('failed to connect MIDI input: %s' % result)
    def on_driver_info(driver):
      def closure(info):
        args = list()
        if ('PARAMETERS' in info):
          params = info['PARAMETERS'].split(',')
          if ('NAME' in params):
            args.append('NAME=LinuxSampler')
        self.call('CREATE MIDI_INPUT_DEVICE %s %s' % 
          (driver, ' '.join(args)), on_connected)
      return(closure)
    def on_drivers(drivers):
      if (not (len(drivers) > 0)):
        self._warn('No MIDI input drivers available.')
        return
      selected = drivers[0]
      for driver in self.preferred_inputs:
        if (driver in drivers):
          selected = driver
          break
      self.call('GET MIDI_INPUT_DRIVER INFO %s' % selected, 
        on_driver_info(selected))    
    self.call('LIST AVAILABLE_MIDI_INPUT_DRIVERS', on_drivers)
  # get the next unused instrument, if any
  def get_instrument(self):
    instrument = Instrument(self)
    self._instruments.append(instrument)
    self.on_change()
    return(instrument)

# make a singleton instance of the sampler backend
LinuxSampler = LinuxSamplerSingleton()

