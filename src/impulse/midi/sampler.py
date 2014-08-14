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

# manage a LinuxSampler process acting as a backend for sample playback
class LinuxSamplerSingleton(observable.Object):
  def __init__(self, 
      preferred_outputs=('ALSA', 'JACK', 'OSS'),
      preferred_inputs=('ALSA', 'JACK', 'OSS')):
    observable.Object.__init__(self)
    self.verbose = False
    self.address = '0.0.0.0'
    self.port = '8888'
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
    self.output_connected = False
    # a socket for communicating with the sampler
    self.connection = None
    self._received = ''
    # queued calls to the sampler
    self._pending_call = None
    self._queued_calls = list()
    # info about the server
    self.server_info = dict()
    # active timeouts
    self.status_timeout = None
    self._receive_timeout = None
    # when started, check the status of the connection by asking for info
    self.call('GET SERVER INFO', self._on_server_info)
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
  # set up audio output
  def _connect_output(self):
    def on_connected(result):
      if (result.startswith('OK') or (result.startswith('WRN'))):
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

# make a singleton instance of the sampler backend
LinuxSampler = LinuxSamplerSingleton()

