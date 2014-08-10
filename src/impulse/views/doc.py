from gi.repository import Gtk
import core
import track
import device
from ..midi import inputs

class DocumentView(Gtk.Frame):
  def __init__(self, document, transport):
    Gtk.Frame.__init__(self)
    self.set_border_width(0)
    self.set_label(None)
    self._document = document
    self._transport = transport
    self.panes = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
    self.add(self.panes)
    self.left_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.left_box.set_border_width(2)
    self.panes.pack1(self.left_box, False, False)
    self.right_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.right_box.set_border_width(2)
    self.panes.pack2(self.right_box, True, True)
    # make layouts for inputs and tracks
    self.input_devices = inputs.InputDeviceList()
    self.input_device_layout = device.DeviceLayout(self.input_devices)
    self.track_layout = track.TrackLayout(self.document.tracks)
    # add a view for input devices
    self.input_list_view = device.DeviceListView(
      devices=self.input_devices, device_layout=self.input_device_layout)
    self.left_box.pack_start(self.input_list_view, False, False, 0)
    self.input_list_view.set_size_request(20, 80)
    # add a patch bay to route between inputs and tracks
    self.input_patch_bay_view = device.PatchBayView(
      patch_bay=self.document.input_patch_bay,
      left_list=self.input_devices, left_layout=self.input_device_layout,
      right_list=self.document.tracks, right_layout=self.track_layout)
    self.left_box.pack_start(self.input_patch_bay_view, False, False, 0)
    self.input_patch_bay_view.set_size_request(80, 80)
    # add a view for arming tracks
    self.track_arms = core.ListView(
      self.document.tracks, view_class=track.TrackArmView,
      list_layout=self.track_layout)
    self.left_box.pack_start(self.track_arms, False, False, 0)
    self.track_arms.set_size_request(40, 80)
    # add a view for track pitches
    self.pitch_keys = core.ListView(
      self.document.tracks, view_class=track.PitchKeyView, 
      list_layout=self.track_layout)
    self.left_box.pack_end(self.pitch_keys, True, True, 0)
    self.pitch_keys.set_size_request(30, 80)
    # add a view for the document's tracks
    self.tracks_view = track.TrackListView(
      tracks=self.document.tracks, 
      track_layout=self.track_layout,
      transport=self.transport)
    self.right_box.pack_start(self.tracks_view, True, True, 0)
  @property
  def document(self):
    return(self._document)
  @property
  def transport(self):
    return(self._transport)
    
  
