#!/usr/bin/env python

import os, sys

from gi.repository import Gtk, Gdk

import doc
import views
import inputs
import controllers
import menu

def dummy_document():
  d = doc.Document()
  e = doc.EventList(duration=4, divisions=8)
  e.append(doc.Note(time=0, duration=0.5, pitch=32))
  e.append(doc.Note(time=0.5, duration=1, pitch=33, velocity=0.75))
  e.append(doc.Note(time=1.5, duration=0, pitch=32, velocity=0.25))
  e.append(doc.Note(time=2, duration=2, pitch=31, velocity=0.5))
  b1 = doc.Block(e, duration=8)
  e2 = doc.EventList(duration=4)
  e2.append(doc.Note(time=0, duration=1, pitch=30))
  b2 = doc.Block(e2, time=10, duration=4)
  t = doc.Track(duration=20)
  t.append(b1)
  t.append(b2)
  d.tracks.append(t)
  t2 = doc.Track(duration=20)
  t2.append(doc.Block(e, time=3, duration=4))
  d.tracks.append(t2)
  return(d)

class DocumentWindow(Gtk.Window):
  def __init__(self):
    Gtk.Window.__init__(self)
    self._document = None
    # set default size
    self.set_default_size(800, 600)
    # make a menu and bind to it
    self._make_menu()
    # make some widgets for the main content
    self.outer_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    self.outer_box.homogenous = False
    self.add(self.outer_box)
    self.outer_box.pack_start(self.menu.toolbar, False, False, 0)
    self.doc_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    self.doc_box.homogenous = False
    self.outer_box.pack_end(self.doc_box, True, True, 0)
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
    self._unbind_menu()
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
    views.ViewManager = views.ViewManagerSingleton()
  # attach to a new document
  def attach(self):
    # make a mixer and transport
    self.mixer = controllers.Mixer(self.document.tracks)
    self.transport = controllers.Transport()
    self.control_surface = inputs.NanoKONTROL2(
      transport=self.transport, mixer=self.mixer)
    # add a view for track headers
    self.track_headers_view = views.TrackListHeaderView(
      tracks=self.document.tracks)
    self.doc_box.pack_start(self.track_headers_view, False, False, 0)
    self.track_headers_view.set_size_request(100, 100)
    # add a view for the document's tracks
    self.tracks_view = views.TrackListView(
      tracks=self.document.tracks, 
      transport=self.transport)
    self.doc_box.pack_end(self.tracks_view, True, True, 0)
    # bind the menu to the new items
    self._bind_menu()
    # show any new views
    self.show_all()
  
  # make a menu
  def _make_menu(self):
    self.menu = menu.Menu(self)
    # keep a list of menu bindings
    self._menu_bindings = [ ]
  # bind menu actions
  def _bind_menu(self):
    # transport
    t = self.transport
    self._bind_action(self.menu.back_action, t.skip_back)
    self._bind_action(self.menu.forward_action, t.skip_forward)
    self._bind_action(self.menu.stop_action, t.stop)
    self._bind_action(self.menu.play_action, t.play)
    self._bind_action(self.menu.record_action, t.record)
    # undo/redo
    vm = views.ViewManager
    self._bind_action(self.menu.undo_action, vm.undo)
    self._bind_action(self.menu.redo_action, vm.redo)
    # update menu state
    self.document.tracks.add_observer(self.update_menu_state)
    vm.add_observer(self.update_menu_state)
    self.update_menu_state()
  # unbind all menu actions
  def _unbind_menu(self):
    for (action, handler) in self._menu_bindings:
      action.disconnect(handler)
    views.ViewManager.remove_observer(self.update_menu_state)
    self.document.tracks.remove_observer(self.update_menu_state)
  # bind to an action and remember the binding
  def _bind_action(self, action, callback):
    handler = action.connect('activate', callback)
    self._menu_bindings.append((action, handler))
  # reflect changes to models in the menu
  def update_menu_state(self):
    vm = views.ViewManager
    self.menu.undo_action.set_sensitive(vm.can_undo)
    self.menu.redo_action.set_sensitive(vm.can_redo)
    # only allow recording if a track is armed
    track_armed = False
    for track in self.document.tracks:
      if (track.arm):
        track_armed = True
        break
    self.menu.record_action.set_sensitive(track_armed)
  
class App:
  def __init__(self):
    self.win = DocumentWindow()
    self.win.document = dummy_document()
    self.win.connect("delete-event", Gtk.main_quit)
    self.win.show_all()
  
  def run(self):
    Gtk.main()

app = App()
app.run()

