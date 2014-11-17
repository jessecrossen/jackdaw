import os
import sys
import time
import re
import subprocess
import fcntl
import atexit
import socket
import jackpatch

from PySide.QtCore import *

import observable
import serializable
import unit

# provide extensions for sample instruments
EXTENSIONS = ('gig', 'sfz', 'sf2')

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
class Instrument(observable.Object, unit.Source, unit.Sink):
  def __init__(self, path=None, name='Instrument', sampler=None):
    observable.Object.__init__(self)
    unit.Source.__init__(self)
    unit.Sink.__init__(self)
    self._source_type = 'stereo'
    self._sink_type = 'midi'
    if (sampler is None):
      global LinuxSampler
      sampler = LinuxSampler
    self._name = name
    self._sampler = sampler
    self._progress = 0
    self._progress_timer = None
    self._path = None
    self._channel = None
    self._channel_connected = False
    self._path_loading = False
    self._path_loaded = False
    self.path = path
  def __del__(self):
    if (self._channel is not None):
      self._sampler.release_channel(self._channel)
      self._channel = None
  @property
  def name(self):
    return(self._name)
  @name.setter
  def name(self, value):
    if (value != self._name):
      self._name = value
      self.on_change()
  @property
  def sink_port(self):
    if (self._channel is None):
      return(None)
    return(self._channel.input_port)
  @property
  def source_port(self):
    if (self._channel is None):
      return(None)
    return(self._channel.output_port)
  @property
  def channel(self):
    return(self._channel)
  @property
  def path(self):
    return(self._path)
  @path.setter
  def path(self, value):
    if (value != self._path):
      self._path_loading = False
      self._path_loaded = False
      self._path = value
      self._name = 'Instrument'
      self._attach()    
  # add a sampler channel for the instrument and load a sample file, if any
  def _attach(self):
    if (self._path is None): return
    m = re.search('\.([^.]+)$', self._path)
    if (not m):
      self._sampler.warn(
        'Unable to find a sampler engine for "%s"' % self._path)
    engine = m.group(1).upper()
    self.name = os.path.basename(self._path)
    # make sure we have a channel with the right engine
    if ((self._channel is None) or (self._channel.engine != engine)):
      if (self._channel is not None):
        self._channel.remove_observer(self._load_path)
        self._channel.remove_observer(self.on_change)
        self._sampler.release_channel(self._channel)
      self._channel = self._sampler.allocate_channel_with_engine(engine)
    # once the channel is ready, load the instrument file onto it
    self._channel.add_observer(self._load_path)
    self._channel.add_observer(self.on_change)
    self._load_path()
  # load a new instrument
  def _load_path(self):
    # if the path is already loaded, we don't need to do anything
    if ((self._path_loading) or (self._path_loaded)): return
    # make sure we have a file to load
    if (self._path is None): return
    # make sure the channel is ready
    if (not self._channel.is_ready): return
    # stop the progress timer if an instrument was being loaded
    if (self._progress_timer is not None):
      self._progress_timer.stop()
      self._progress_timer = None
    # reset the progress
    self._progress = 0
    # start loading the instrument from the current path
    self._path_loading = True
    self._sampler.call('LOAD INSTRUMENT NON_MODAL "%s" 0 %d' %
      (_escape(self._path), self._channel._channel_id), self._on_load_start)
  # handle the instrument beginning to load
  def _on_load_start(self, result):
    if (result.startswith('OK')):
      self._path_loading = True
      self._progress_timer = QTimer(self)
      self._progress_timer.timeout.connect(self._update_progress)
      self._progress_timer.start(500)
    else:
      self._path_loading = False
  # check for progress in loading the instrument
  def _update_progress(self):
    # see if we're finished loading
    if ((self._progress >= 100) or (self._progress < 0)):
      self._progress_timer.stop()
      self._progress_timer = None
      self._path_loading = False
      self._path_loaded = (self._progress >= 100)
      return
    # ask for another progress report
    self._sampler.call('GET CHANNEL INFO %d' % self._channel.channel_id, 
      self._on_progress)
  def _on_progress(self, result):
    if ((result) and ('INSTRUMENT_STATUS' in result)):
      self._progress = int(result['INSTRUMENT_STATUS'])
  def serialize(self):
    return({ 
      'name': self.name,
      'path': self.path
    })
serializable.add(Instrument)

class InstrumentList(observable.List):
  def __init__(self, instruments=()):
    observable.List.__init__(self, instruments)
  # adapter list serialization
  def serialize(self):
    return({ 
      'instruments': list(self)
    })
serializable.add(InstrumentList)

# manage a MIDI input device in LinuxSampler
class SamplerInput(observable.Object):
  def __init__(self, sampler=None, name=None):
    observable.Object.__init__(self)
    if (sampler is None):
      global LinuxSampler
      sampler = LinuxSampler
    self._sampler = sampler
    self._name = name
    self._input_id = None
    # this is used to cache the JACK port associated with the input
    self.port = None
    self._allocate()
  @property
  def input_id(self):
    return(self._input_id)
  @property
  def name(self):
    return(self._name)
  # allocate a midi input device
  def _allocate(self):
    command = 'CREATE MIDI_INPUT_DEVICE JACK'
    if (self._name is not None):
      command += ' NAME='+self._name
    self._sampler.call(command, self._on_created)
  # handle the creation of the input device
  def _on_created(self, result):
    if (result.startswith('OK') or (result.startswith('WRN'))):
      m = re.match('OK\[(.*)\]', result)
      if (m):
        self._input_id = int(m.group(1))
        self.on_change()
      self.on_change()
    else:
      self._sampler.warn('failed to connect MIDI input: %s' % result)    

# manage an audio output device in LinuxSampler
class SamplerOutput(observable.Object):
  def __init__(self, engine='GIG', sampler=None, name=None):
    observable.Object.__init__(self)
    if (sampler is None):
      global LinuxSampler
      sampler = LinuxSampler
    self._sampler = sampler
    self._name = name
    self._output_id = None
    # this is used to cache the JACK port(s) associated with the output
    self.port = None
    self._allocate()
  @property
  def output_id(self):
    return(self._output_id)
  @property
  def name(self):
    return(self._name)
  # allocate an audio output device
  def _allocate(self):
    command = 'CREATE AUDIO_OUTPUT_DEVICE JACK'
    if (self._name is not None):
      command += ' NAME='+self._name
    self._sampler.call(command, self._on_created)
  # handle the creation of the audio output device
  def _on_created(self, result):
    if (result.startswith('OK') or (result.startswith('WRN'))):
      m = re.match('OK\[(.*)\]', result)
      self._output_id = int(m.group(1))
      self.on_change()
    else:
      self._sampler.warn('failed to connect audio output: %s' % result)

# manage a sampler "channel" in LinuxSampler
class SamplerChannel(observable.Object):
  def __init__(self, engine='GIG', sampler=None):
    observable.Object.__init__(self)
    if (sampler is None):
      global LinuxSampler
      sampler = LinuxSampler
    self._sampler = sampler
    self._channel_id = None
    self._engine = engine
    self._engine_loaded = False
    # start with no input or output
    self._input = None
    self._input_connected = False
    self._input_connecting = False
    self._input_port = None
    self._output = None
    self._output_connected = False
    self._output_connecting = False
    self._output_port = None
    # load the right sampler engine and allocate a channel id
    self._allocate()
  @property
  def channel_id(self):
    return(self._channel_id)
  @property
  def engine(self):
    return(self._engine)
  @property
  def is_ready(self):
    return(self._engine_loaded and 
           self._input_connected and 
           self._output_connected)
  @property
  def input_port(self):
    return(self._input_port)
  @property
  def output_port(self):
    return(self._output_port)
  # allocate a new sampler channel
  def _allocate(self):
    self._sampler.call('ADD CHANNEL', self._on_channel_add)
  def _on_channel_add(self, result):
    m = re.match('OK\[(.*)\]', result)
    if (m):
      self._channel_id = int(m.group(1))
      self.on_change()
      self._load_engine()
    else:
      self._sampler.warn('failed to add channel: %s' % str(result))
  # load a sampler engine for the channel
  def _load_engine(self):
    self._sampler.call('LOAD ENGINE %s %d' % 
      (self.engine, self.channel_id), self._on_engine_load)
  def _on_engine_load(self, result):
    if (result == 'OK'):
      self._engine_loaded = True
      self.on_change()
    else:
      self._sampler.warn('failed to load sampler engine %s: %s' % 
                            (self.engine, str(result)))
  # make a property to get or set the input device
  @property
  def input(self):
    return(self._input)
  @input.setter
  def input(self, value):
    if (value is self._input): return
    if (self._input is not None):
      self._input.remove_observer(self)
      self._input_connected = False
    self._input = value
    self._input_port = self._input.port
    if (self._input is not None):
      self._input.add_observer(self._connect_input)
      self._connect_input()
  # connect the input when it's available
  def _connect_input(self):
    if ((not self._input_connected) and 
        (not self._input_connecting) and 
        (self._input.input_id is not None)):
      self._input_connecting = True
      self._sampler.call(
        'SET CHANNEL MIDI_INPUT_DEVICE %d %d' % 
          (self.channel_id, self._input.input_id), self._on_input_set)
  def _on_input_set(self, result):
    self._input_connecting = False
    if (result.startswith('OK')):
      self._input_connected = True
      # attempt to bind to the input to a JACK port
      if (self._input_port is None):
        ports = self._sampler._client.get_ports(
          name_pattern=self._input.name+':.*',
          flags=jackpatch.JackPortIsInput)
        if (len(ports) > 0):
          self._input.port = ports[0]
          self._input_port = self._input.port
      self.on_change()
    else:
      self._sampler.warn('failed to set channel input: %s' % str(result))
  # make a property to get or set the output device
  @property
  def output(self):
    return(self._output)
  @output.setter
  def output(self, value):
    if (value is self._output): return
    if (self._output is not None):
      self._output.remove_observer(self)
      self._output_connected = False
    self._output = value
    self._output_port = self._output.port
    if (self._output is not None):
      self._output.add_observer(self._connect_output)
      self._connect_output()
  # connect the output when it's available
  def _connect_output(self):
    if ((not self._output_connected) and 
        (not self._output_connecting) and 
        (self._output.output_id is not None)):
      self._output_connecting = True
      self._sampler.call(
        'SET CHANNEL AUDIO_OUTPUT_DEVICE %d %d' % 
          (self.channel_id, self._output.output_id), self._on_output_set)
  def _on_output_set(self, result):
    self._output_connecting = False
    if (result.startswith('OK')):
      self._output_connected = True
      if (self._output_port is None):
        ports = self._sampler._client.get_ports(
          name_pattern=self._output.name+':.*',
          flags=jackpatch.JackPortIsOutput)
        if (len(ports) == 1):
          self._output.port = ports[0]
        elif (len(ports) >= 2):
          self._output.port = tuple(ports[0:2])
        self._output_port = self._output.port
      self.on_change()
    else:
      self._sampler.warn('failed to set channel output: %s' % str(result))

# manage a LinuxSampler process acting as a backend for sample playback
class LinuxSamplerSingleton(observable.Object):
  def __init__(self, verbose=False):
    observable.Object.__init__(self)
    self.verbose = verbose
    self.address = '0.0.0.0'
    self.port = '8888'
    self.device_id = None
    # make a JACK client for querying ports
    self._client = jackpatch.Client('jackdaw-sampler')
    self._reset()
  # log activity
  def _log(self, message):
    if (self.verbose):
      print(message)
  def warn(self, message):
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
    # a socket for communicating with the sampler
    self.connection = None
    self._received = ''
    # queued calls to the sampler
    self._pending_call = None
    self._queued_calls = list()
    # info about the server
    self.server_info = dict()
    self.engines = list()
    # active timers
    self._status_timer = None
    self._receive_timer = None
    # a list of unused sampler channels
    self._unused_channels_by_engine = dict()
    # a unique numeric id to assign created input/output ports
    self._unique_port_id = 1
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
    self._status_timer = QTimer(self)
    self._status_timer.timeout.connect(self._check_status)
    self._status_timer.start(1000)
  # stop running the service
  def stop(self):
    if (not self.process): return
    # stop timeouts
    if (self._status_timer):
      self._status_timer.stop()
    elif (self._receive_timer):
      self._receive_timer.stop()
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
      self._status_timer = None
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
    self.warn(error)
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
    self._receive_timer = QTimer(self)
    self._receive_timer.timeout.connect(self._receive)
    self._receive_timer.start(100)
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
        self.warn(line)
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
      self._receive_timer = None
    return(False)
  # respond to getting the first info from the server
  def _on_server_info(self, info):
    self.server_info.update(info)
    # once we get this, we should be ready to rock and roll
    self._log('sampler is ready')
    self.ready = True
    self.on_change()
  def _on_engines(self, engines):
    self.engines = engines
  # allocate a new sampler channel or get an unused one from the pool
  def allocate_channel_with_engine(self, engine):
    if (engine in self._unused_channels_by_engine):
      channels = self._unused_channels_by_engine[engine]
      if (len(channels) > 0):
        return(channels.pop())
    # make a name for the channel's input/output JACK client
    name = 'LinuxSampler-'+str(self._unique_port_id)
    self._unique_port_id += 1
    # make the channel and give it input and output
    channel = SamplerChannel(engine=engine, sampler=self)
    channel.input = SamplerInput(sampler=self, name=name)
    channel.output = SamplerOutput(sampler=self, name=name)
    return(channel)
  # release a previously allocated channel for reuse
  def release_channel(self, channel):
    if (channel.engine not in self._unused_channels_by_engine):
      self._unused_channels_by_engine[channel.engine] = list()
    self._unused_channels_by_engine[channel.engine].append(channel)

# make a singleton instance of the sampler backend
LinuxSampler = LinuxSamplerSingleton(verbose=False)

