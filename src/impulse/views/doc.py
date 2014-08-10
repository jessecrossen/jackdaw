from gi.repository import Gtk
import core
import track
import device
from ..midi import inputs, outputs

class DocumentView(Gtk.Frame):
  def __init__(self, document, transport):
    Gtk.Frame.__init__(self)
    self.set_border_width(0)
    self.set_label(None)
    self._document = document
    self._transport = transport
    # make layouts for inputs and tracks
    self.input_devices = inputs.InputDeviceList()
    self.output_devices = outputs.OutputDeviceList()
    self.input_device_layout = device.DeviceLayout(self.input_devices)
    self.output_device_layout = device.DeviceLayout(self.output_devices)
    self.track_layout = track.TrackLayout(self.document.tracks)
    # build the left panel
    self.input_list_view = core.ListView(
      self.input_devices, view_class=device.DeviceView, 
      list_layout=self.input_device_layout)
    self.input_list_view.set_size_request(20, -1)
    transition = core.ListView(
      self.input_devices,
      view_class=track.ToSignalTransitionView,
      list_layout=self.input_device_layout)
    transition.set_size_request(12, -1)
    self.input_patch_bay_view = device.PatchBayView(
      patch_bay=self.document.input_patch_bay,
      left_list=self.input_devices, left_layout=self.input_device_layout,
      right_list=self.document.tracks, right_layout=self.track_layout)
    self.input_patch_bay_view.set_size_request(60, -1)
    self.inputs_column = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.inputs_column.pack_start(self.input_list_view, False, False, 0)
    self.inputs_column.pack_start(transition, False, False, 0)
    self.inputs_column.pack_start(self.input_patch_bay_view, True, True, 0)
    self.track_arms = core.ListView(
      self.document.tracks, view_class=track.TrackArmView,
      list_layout=self.track_layout)
    self.track_arms.set_size_request(40, -1)
    transition = core.ListView(
      self.document.tracks,
      view_class=track.FromSignalTransitionView,
      list_layout=self.track_layout)
    transition.set_size_request(12, -1)
    self.left_panel = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.left_panel.pack_start(self.inputs_column, True, True, 0) 
    self.left_panel.pack_start(self.track_arms, False, False, 0)
    self.left_panel.pack_start(transition, False, False, 0)
    # set up the center panel
    self.pitch_keys = core.ListView(
      self.document.tracks, view_class=track.PitchKeyView, 
      list_layout=self.track_layout)
    self.pitch_keys.set_size_request(30, -1)
    self.tracks_view = track.TrackListView(
      tracks=self.document.tracks, 
      track_layout=self.track_layout,
      transport=self.transport)
    self.center_panel = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
    self.center_panel.pack_start(self.pitch_keys, False, False, 0)
    self.center_panel.pack_start(self.tracks_view, True, True, 0)
    # set up the right panel
    self.mixer_view = core.ListView(
      self.document.tracks, view_class=track.TrackMixerView,
      list_layout=self.track_layout)
    self.mixer_view.set_size_request(40, -1)
    self.output_patch_bay_view = device.PatchBayView(
      patch_bay=self.document.output_patch_bay,
      left_list=self.document.tracks, left_layout=self.track_layout,
      right_list=self.output_devices, right_layout=self.output_device_layout)
    self.output_patch_bay_view.set_size_request(60, -1)
    transition = core.ListView(
      self.output_devices,
      view_class=track.FromSignalTransitionView,
      list_layout=self.output_device_layout)
    transition.set_size_request(12, -1)
    self.output_list_view = core.ListView(
      self.output_devices, view_class=device.DeviceView, 
      list_layout=self.output_device_layout)
    self.output_list_view.set_size_request(20, -1)
    self.outputs_column = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.outputs_column.pack_start(self.output_patch_bay_view, True, True, 0)
    self.outputs_column.pack_start(transition, False, False, 0)
    self.outputs_column.pack_start(self.output_list_view, False, False, 0)
    transition = core.ListView(
      self.document.tracks,
      view_class=track.ToSignalTransitionView,
      list_layout=self.track_layout)
    transition.set_size_request(12, -1)
    self.right_panel = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.right_panel.pack_start(transition, False, False, 0)
    self.right_panel.pack_start(self.mixer_view, False, False, 0)
    self.right_panel.pack_start(self.outputs_column, True, True, 0)
    # set up the main layout structure
    self.root = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
    self.root.pack_start(self.left_panel, False, False, 0)
    self.root.pack_start(self.center_panel, True, True, 0)
    self.root.pack_start(self.right_panel, False, False, 0)
    self.add(self.root)
  
  @property
  def document(self):
    return(self._document)
  @property
  def transport(self):
    return(self._transport)
    
  
