#!/usr/bin/env python

import doc

def note_changed():
  print "note_changed"
def list_changed():
  print "list_changed"

x = doc.ModelList()
x.add_listener(list_changed)

n = doc.Note(duration=1)
print n.duration

n.add_listener(note_changed)
n.duration = 2

x.append(n)

n.duration = 3
