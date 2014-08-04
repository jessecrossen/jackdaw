import os, sys

from gi.repository import Gtk, Gdk, Gio

from models import doc, controllers
import views.track
from views.core import ViewManager
from midi import inputs

class DocumentWindow(Gtk.ApplicationWindow):
  def __init__(self, app):
    Gtk.ApplicationWindow.__init__(self, application=app,
                                         title="Impulse")
    self._document = None
    # bind to the application
    self.app = app
    # set default size
    self.set_default_size(800, 600)
    # make a toolbar
    self._make_actions()
    self._make_toolbar()
    # make some widgets for the main content
    self.outer_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    self.outer_box.homogenous = False
    self.add(self.outer_box)
    self.outer_box.pack_start(self.toolbar, False, False, 0)
    self.panes = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
    self.outer_box.pack_end(self.panes, True, True, 0)
    self.header_frame = Gtk.Frame.new('')
    self.header_frame.set_border_width(2)
    self.panes.pack1(self.header_frame, False, False)
    self.tracks_frame = Gtk.Frame.new('')
    self.tracks_frame.set_border_width(2)
    self.panes.pack2(self.tracks_frame, True, True)
    # initialize state
    self.control_surface = None
    self.transport = None
    self.mixer = None
    self.tracks_view = None
    self.track_headers_view = None
    self.document = doc.Document()
    
  @property
  def document(self):
    return(self._document)
  @document.setter
  def document(self, value):
    # detach from the old document
    if (self._document is not None):
      self.detach()
      self._document = None
    # attach to the new document
    if (value is not None):
      self._document = value
      self.attach()
  # detach from the current document
  def detach(self):
    self._unbind_actions()
    # detach from the old document
    self.transport = None
    self.mixer = None
    if (self.control_surface):
      self.control_surface.disconnect()
    self.control_surface = None
    if (self.tracks_view):
      self.tracks_view.destroy()
      self.tracks_view = None
    if (self.track_headers_view):
      self.track_headers_view.destroy()
      self.track_headers_view = None
    # dump the undo stack and clear the selection
    ViewManager.reset()
  # attach to a new document
  def attach(self):
    # make a mixer and transport
    self.mixer = controllers.Mixer(self.document.tracks)
    self.transport = controllers.Transport()
    self.control_surface = inputs.NanoKONTROL2(
      transport=self.transport, mixer=self.mixer)
    # add a view for track headers
    self.track_headers_view = views.track.TrackListHeaderView(
      tracks=self.document.tracks)
    self.header_frame.add(self.track_headers_view)
    self.track_headers_view.set_size_request(90, 80)
    # add a view for the document's tracks
    self.tracks_view = views.track.TrackListView(
      tracks=self.document.tracks, 
      transport=self.transport)
    self.tracks_frame.add(self.tracks_view)
    # bind actions for the new document
    self._bind_actions()
    # show the new controls
    self.show_all()
  
  # make actions on the document
  def _make_actions(self):
    # undo/redo actions
    self.undo_action = self.make_action('undo', '<Control>z')
    self.redo_action = self.make_action('redo', '<Control><Shift>z')
    # transport actions
    self.back_action = self.make_action('transportBack')
    self.forward_action = self.make_action('transportForward')
    self.stop_action = self.make_action('transportStop')
    self.play_action = self.make_action('transportPlay')
    self.record_action = self.make_action('transportRecord')
    # keep a list of action bindings so we can unbind them later
    self._action_bindings = [ ]
  # make an action with an optional accelerator
  def make_action(self, name, accel=None):
    action = Gio.SimpleAction.new(name, None)
    if (accel):
      self.app.add_accelerator(accel, 'win.'+name, None)
    self.add_action(action)
    return(action)
  # bind document actions
  def _bind_actions(self):
    # undo/redo
    self._bind_action(self.undo_action, ViewManager.undo)
    self._bind_action(self.redo_action, ViewManager.redo)
    # transport
    t = self.transport
    self._bind_action(self.back_action, t.skip_back)
    self._bind_action(self.forward_action, t.skip_forward)
    self._bind_action(self.stop_action, t.stop)
    self._bind_action(self.play_action, t.play)
    self._bind_action(self.record_action, t.record)
    # update action state
    self.document.tracks.add_observer(self.update_actions)
    ViewManager.add_observer(self.update_actions)
    self.update_actions()
  # unbind all actions
  def _unbind_actions(self):
    for (action, handler) in self._action_bindings:
      action.disconnect(handler)
    ViewManager.remove_observer(self.update_actions)
    self.document.tracks.remove_observer(self.update_actions)
  # bind to an action and remember the binding
  def _bind_action(self, action, callback):
    handler = action.connect('activate', callback)
    self._action_bindings.append((action, handler))
  # reflect changes to models in the action buttons
  def update_actions(self):
    self.undo_action.set_enabled(ViewManager.can_undo)
    self.redo_action.set_enabled(ViewManager.can_redo)
    # only allow recording if a track is armed
    track_armed = False
    for track in self.document.tracks:
      if (track.arm):
        track_armed = True
        break
    self.record_action.set_enabled(track_armed)
  # make a toolbar with document actions
  def _make_toolbar(self):
    # make a toolbar
    t = Gtk.Toolbar.new()
    self.toolbar = t
    # transport actions
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_REWIND, 
                         action_name='win.transportBack'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_FORWARD, 
                         action_name='win.transportForward'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_STOP, 
                         action_name='win.transportStop'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY, 
                         action_name='win.transportPlay'))
    t.add(Gtk.ToolButton(Gtk.STOCK_MEDIA_RECORD, 
                         action_name='win.transportRecord'))
    t.add(Gtk.SeparatorToolItem())
    # undo/redo
    t.add(Gtk.ToolButton(Gtk.STOCK_UNDO, action_name='win.undo'))
    t.add(Gtk.ToolButton(Gtk.STOCK_REDO, action_name='win.redo'))

