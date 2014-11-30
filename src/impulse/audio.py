import jackpatch

import observable
import serializable
import unit

class SystemPlaybackUnit(unit.Sink, unit.Unit):
  def __init__(self, *args, **kwargs):
    unit.Unit.__init__(self, *args, **kwargs)
    unit.Sink.__init__(self)
    self._sink_type = 'stereo'
    self._client = jackpatch.Client('jackdaw-playback')
    ports = self._client.get_ports(name_pattern='system:.*', 
                                   flags=jackpatch.JackPortIsInput)
    self._sink_port = tuple(ports)
serializable.add(SystemPlaybackUnit)