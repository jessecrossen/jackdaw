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
    self.left_panel = core.SwitchableColumnView((
        self.inputs_column, 
        self.track_arms,
        transition),
      toggle_icons=( 
        Gtk.STOCK_CONNECT,
        Gtk.STOCK_DISCONNECT))
    # set up the center panel
    self.pitch_keys = core.ListView(
      self.document.tracks, view_class=track.PitchKeyView, 
      list_layout=self.track_layout)
    self.pitch_keys.set_size_request(30, -1)
    self.tracks_view = track.TrackListView(
      tracks=self.document.tracks, 
      track_layout=self.track_layout,
      transport=self.transport)
    self.center_panel = core.SwitchableColumnView((
        self.pitch_keys, 
        self.tracks_view), 
      expandable=self.tracks_view,
      toggle_icons=(
        Gtk.STOCK_ITALIC,
        Gtk.STOCK_JUSTIFY_FILL),
      spacing=4)
    self.center_panel.toolbar.add(Gtk.SeparatorToolItem())
    self.add_toolbar_items(self.center_panel.toolbar)
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
    self.right_panel = core.SwitchableColumnView((
        transition,
        self.mixer_view,
        self.outputs_column),
      toggle_icons=(None, Gtk.STOCK_BOLD, Gtk.STOCK_GO_FORWARD))
    # set up the main layout structure
    self.root = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 4)
    self.root.pack_start(self.left_panel, False, False, 0)
    self.root.pack_start(self.center_panel, True, True, 0)
    self.root.pack_start(self.right_panel, False, False, 0)
    self.add(self.root)
  # build the toolbar
  def add_toolbar_items(self, toolbar):
    # transport actions
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_REWIND, 
                         action_name='win.transportBack'))
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_FORWARD, 
                         action_name='win.transportForward'))
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_STOP, 
                         action_name='win.transportStop'))
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY, 
                         action_name='win.transportPlay'))
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_RECORD, 
                         action_name='win.transportRecord'))
    toolbar.add(Gtk.SeparatorToolItem())
    # undo/redo
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_UNDO, action_name='win.undo'))
    toolbar.add(Gtk.ToolButton(Gtk.STOCK_REDO, action_name='win.redo'))
  
  @property
  def document(self):
    return(self._document)
  @property
  def transport(self):
    return(self._transport)
    
  
