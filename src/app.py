#!/usr/bin/env python

from gi.repository import Gtk, Gdk

from impulse import windows
from impulse.models import doc

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

class App:
  def __init__(self):
    self.win = windows.DocumentWindow()
    self.win.document = dummy_document()
    self.win.connect("delete-event", Gtk.main_quit)
    self.win.show_all()
  
  def run(self):
    Gtk.main()

app = App()
app.run()
