import unittest

from PySide.QtCore import QObject, Signal

# make an object which can report changes to itself
class Object(QObject):
  changed = Signal()
  def __init__(self):
    QObject.__init__(self)
    self._change_block_level = 0
  def add_observer(self, slot):
    self.changed.connect(slot)
  def remove_observer(self, slot):
    self.changed.disconnect(slot)
  def on_change(self):
    if (self._change_block_level <= 0):
      self.changed.emit()
  # wrap a block of changes in the following calls to ensure that the changed 
  #  signal only gets emitted once at the end instead of for each change
  def begin_change_block(self):
    self._change_block_level += 1
  def end_change_block(self):
    self._change_block_level = max(0, self._change_block_level - 1)
    if (self._change_block_level == 0):
      self.on_change()
    
# overlay the observable property onto an existing QObject
class Mixin(QObject):
  changed = Signal()
  def add_observer(self, slot):
    self.changed.connect(slot)
  def remove_observer(self, slot):
    self.changed.disconnect(slot)
  def on_change(self):
    self.changed.emit()

# make a list which can report changes to itself or its members
class List(Object):
  def __init__(self, seq=()):
    Object.__init__(self)
    self._items = list(seq)
    for item in self._items:
      self._add_item(item)
  # make this hashable so it can receive callbacks
  def __hash__(self):
    return(id(self))
  # proxy read-only list methods
  def __len__(self):
    return(len(self._items))
  def __getitem__(self, key):
    return(self._items.__getitem__(key))
  def __getslice__(self, i, j):
    return(self._items.__getslice__(i, j))
  def __contains__(self, x):
    return(self._items.__contains__(x))
  def __iter__(self):
    return(self._items.__iter__())
  def count(self, x):
    return(self._items.count(x))
  # proxy list methods to detect changes
  def __setitem__(self, key, item):
    try:
      old_item = self._items.__getitem__(key)
      self._remove_item(old_item)
    except KeyError:
      pass
    self._items.__setitem__(key, item)
    self._add_item(item)
    self.on_change()
  def __setslice__(self, i, j, new_items):
    old_slice = self._items.__getslice__(i, j)
    if (old_slice):
      for item in old_slice:
        self._remove_item(item)
    self._items.__setslice__(i, j, new_items)
    for item in new_items:
      self._add_item(item)
    self.on_change()
  def __delitem__(self, key):
    self._remove_item(self._items.__getitem__(key))
    self._items.__delitem__(key)
    self.on_change()
  def __delslice__(self, i, j):
    old_slice = self._items.__getslice__(i, j)
    if (old_slice):
      for item in old_slice:
        self._remove_item(item)
    self._items.__delslice__(i, j)
    self.on_change()
  def append(self, item):
    self._items.append(item)
    self._add_item(item)
    self.on_change()
  def pop(self, i=None):
    if (i == None):
      item = self._items.pop()
    else:
      item = self._items.pop(i)
    self._remove_item(item)
    self.on_change()
    return(item)
  def extend (self, new_items):
    for item in new_items:
      self._add_item(item)
    self._items.extend(new_items)
    self.on_change()
  def insert (self, i, item):
    self._items.insert(i, item)
    self._add_item(item)
    self.on_change()
  def remove(self, item):
    self._items.remove(item)
    self._remove_item(item)
    self.on_change()
  def reverse(self):
    self._items.reverse()
    self.on_change()
  def sort(self, **kwargs):
    self._items.sort(**kwargs)
    self.on_change()
  # handle models being added and removed from the list
  def _add_item(self, item):
    try:
      item.add_observer(self.on_change)
    except AttributeError: pass
  def _remove_item(self, item):
    try:
      item.remove_observer(self.on_change)
    except AttributeError: pass

# make an object that exposes observable attributes for another object
class AttributeProxy(Object):
  def __init__(self, target, from_name=None, to_name=None):
    Object.__init__(self)
    self._target = target
    self._attribute_map = dict()
    self.proxy_attribute(from_name, to_name)
  @property
  def target(self):
    return(self._target)
  # proxy an attribute, optionally using a different name for the target
  def proxy_attribute(self, from_name, to_name=None):
    if (from_name is None): return
    if (to_name is None):
      to_name = from_name
    self._attribute_map[from_name] = to_name
  # proxy attributes
  def __getattr__(self, name):
    if (name in self._attribute_map):
      name = self._attribute_map[name]
    return(getattr(self._target, name))
  def __setattr__(self, name, value):
    if ((hasattr(self, '_attribute_map')) and 
        (name in self._attribute_map)):
      name = self._attribute_map[name]
      old_value = getattr(self._target, name)
      if (value != old_value):
        setattr(self._target, name, value)
        self.on_change()
    elif ((hasattr(self, '_target')) and 
          (hasattr(self._target, name))):
      setattr(self._target, name, value)
    object.__setattr__(self, name, value)

# TESTS #######################################################################

class TestObject(unittest.TestCase):
  def setUp(self):
    self.obj = Object()
    self.changes = 0
  # make a change handler that counts changes for each test
  def on_change(self):
    self.changes += 1
  # test listening to the object's changes
  def test_no_listener(self):
    self.obj.on_change()
    self.assertEqual(self.changes, 0)
  def test_listener(self):
    self.obj.add_observer(self.on_change)
    self.obj.on_change()
    self.assertEqual(self.changes, 1)
    self.obj.remove_observer(self.on_change)
    self.obj.on_change()
    self.assertEqual(self.changes, 1)
    
class TestList(unittest.TestCase):
  def setUp(self):
    self.itemA = Object()
    self.itemB = Object()
    self.itemC = Object()
    self.itemD = Object()
    self.list = List()
    self.changes = 0
  # make a change handler that counts changes for each test
  def on_change(self):
    self.changes += 1
  # test listening to the object's changes
  def test_no_listener(self):
    self.list.on_change()
    self.assertEqual(self.changes, 0)
  def test_listener(self):
    self.list.add_observer(self.on_change)
    self.list.on_change()
    self.assertEqual(self.changes, 1)
    self.list.remove_observer(self.on_change)
    self.list.on_change()
    self.assertEqual(self.changes, 1)
  # test list operations
  def test_replace(self):
    self.list.append(self.itemA)
    self.list.add_observer(self.on_change)
    self.list[0] = self.itemB
    self.assertNotIn(self.itemA, self.list)
    self.assertIn(self.itemB, self.list)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.assertEqual(self.changes, 1)
    self.itemB.on_change()
    self.assertEqual(self.changes, 2)
  def test_replace_slice(self):
    self.list.append(self.itemA)
    self.list.append(self.itemB)
    self.list.append(self.itemC)
    self.list.add_observer(self.on_change)
    self.list[0:2] = [self.itemD]
    self.assertNotIn(self.itemA, self.list)
    self.assertNotIn(self.itemB, self.list)
    self.assertIn(self.itemC, self.list)
    self.assertIn(self.itemD, self.list)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.itemB.on_change()
    self.assertEqual(self.changes, 1)
    self.itemC.on_change()
    self.itemD.on_change()
    self.assertEqual(self.changes, 3)
  def test_delete(self):
    self.list.append(self.itemA)
    self.list.add_observer(self.on_change)
    del self.list[0]
    self.assertNotIn(self.itemA, self.list)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.assertEqual(self.changes, 1)
  def test_delete_slice(self):
    self.list.append(self.itemA)
    self.list.append(self.itemB)
    self.list.append(self.itemC)
    self.list.add_observer(self.on_change)
    del self.list[0:2]
    self.assertNotIn(self.itemA, self.list)
    self.assertNotIn(self.itemB, self.list)
    self.assertIn(self.itemC, self.list)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.itemB.on_change()
    self.assertEqual(self.changes, 1)
    self.itemC.on_change()
    self.assertEqual(self.changes, 2)
  def test_append(self):
    self.list.add_observer(self.on_change)
    self.list.append(self.itemA)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.assertEqual(self.changes, 2)
  def test_pop(self):
    self.list.append(self.itemA)
    self.list.add_observer(self.on_change)
    item = self.list.pop()
    self.assertIs(item, self.itemA)
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.assertEqual(self.changes, 1)
  def test_extend(self):
    self.list.add_observer(self.on_change)
    self.list.extend((self.itemA, self.itemB))
    self.assertEqual(self.changes, 1)
    self.assertIn(self.itemA, self.list)
    self.assertIn(self.itemB, self.list)
    self.itemA.on_change()
    self.itemB.on_change()
    self.assertEqual(self.changes, 3)
  def test_insert(self):
    self.list.extend((self.itemA, self.itemC))
    self.list.add_observer(self.on_change)
    self.list.insert(1, self.itemB)
    self.assertEqual(self.changes, 1)
    self.assertIn(self.itemA, self.list)
    self.assertIn(self.itemB, self.list)
    self.assertIn(self.itemC, self.list)
    self.itemA.on_change()
    self.itemB.on_change()
    self.itemC.on_change()
    self.assertEqual(self.changes, 4)
  def test_remove(self):
    self.list.extend((self.itemA, self.itemB))
    self.list.add_observer(self.on_change)
    self.list.remove(self.itemB)
    self.assertEqual(self.changes, 1)
    self.assertIn(self.itemA, self.list)
    self.assertNotIn(self.itemB, self.list)
    self.itemB.on_change()
    self.assertEqual(self.changes, 1)
    self.itemA.on_change()
    self.assertEqual(self.changes, 2)
  def test_reverse(self):
    self.list.extend((self.itemA, self.itemB))
    self.list.add_observer(self.on_change)
    self.list.reverse()
    self.assertEqual(self.changes, 1)
    self.assertIn(self.itemA, self.list)
    self.assertIn(self.itemB, self.list)
    self.itemA.on_change()
    self.itemB.on_change()
    self.assertEqual(self.changes, 3)
  def test_sort(self):
    self.itemB.order = 1
    self.itemA.order = 2
    self.list.extend((self.itemA, self.itemB))
    self.list.add_observer(self.on_change)
    self.list.sort(cmp=lambda a, b: a.order - b.order)
    self.assertEqual(self.changes, 1)
    self.assertIs(self.list[0], self.itemB)
    self.assertIs(self.list[1], self.itemA)
    self.itemA.on_change()
    self.itemB.on_change()
    self.assertEqual(self.changes, 3)

# run tests if this script is invoked by itself
if __name__ == '__main__':
  unittest.main()
