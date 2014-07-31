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
    # set default size
    self.set_default_size(800, 600)
    # make a menu and bind to it
    self._bind_menu()
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
    self.document = doc.Document()
    
  @property
  def document(self):
    return(self._document)
  @document.setter
  def document(self, value):
    # detach from the old document
    self.detach()
    self._document = None
    # attach to the new document
    if (value is not None):
      self._document = value
      self.attach()
  # detach from the current document
  def detach(self):
    # detach from the old document
    self.transport = None
    self.mixer = None
    if (self.control_surface):
      self.control_surface.disconnect()
    self.control_surface = None
    if (self.tracks_view):
      self.tracks_view.destroy()
      self.tracks_view = None
  # attach to a new document
  def attach(self):
    # make a mixer and transport
    self.mixer = controllers.Mixer(self.document.tracks)
    self.transport = controllers.Transport()
    self.control_surface = inputs.NanoKONTROL2(
      transport=self.transport, mixer=self.mixer)
    # add a view for the document's tracks
    self.tracks_view = views.TrackListView(tracks=self.document.tracks, 
                                           transport=self.transport,
                                           mixer=self.mixer)
    self.doc_box.pack_end(self.tracks_view, True, True, 0)
    # show any new views
    self.show_all()
  
  # make a menu and bind to its actions
  def _bind_menu(self):
    self.menu = menu.Menu(self)
    # add bindings
    vm = views.ViewManager
    self.menu.undo_action.connect('activate', vm.undo)
    self.menu.redo_action.connect('activate', vm.redo)
    # listen to global state changes so we can activate/deactivate 
    #  menu actions
    vm.add_listener(self.update_menu_state)
    self.update_menu_state()
  # handle changes to the selection, undo stack, etc
  def update_menu_state(self):
    vm = views.ViewManager
    self.menu.undo_action.set_sensitive(vm.can_undo)
    self.menu.redo_action.set_sensitive(vm.can_redo)
  
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

