import unittest

# a mixin to provide basic observer functionality
class Observable():
  # add/remove a callback to be called when the object changes
  def add_observer(self, callback):
    try:
      self._listeners.add(callback)
    except AttributeError:
      self._listeners = set((callback,))
  def remove_observer(self, callback):
    try:
      self._listeners.remove(callback)
    except AttributeError:
      self._listeners = set()
  # call this to notify all listeners that the object changed
  def on_change(self):
    try:
      listeners = self._listeners
    except AttributeError:
      listeners = self._listeners = set()
    for callback in listeners:
      callback()

# make an object which can report changes to itself
class Object(Observable, object):
  pass

# make a list which can report changes to itself or its members
class List(Observable, list):
  # make this hashable so it can receive callbacks
  def __hash__(self):
    return(id(self))
  # proxy list methods to detect changes
  def __setitem__(self, key, item):
    try:
      old_item = list.__getitem__(self, key)
      self._remove_item(old_item)
    except KeyError:
      pass
    list.__setitem__(self, key, item)
    self._add_item(item)
    self.on_change()
  def __setslice__(self, i, j, new_items):
    old_slice = list.__getslice__(self, i, j)
    if (old_slice):
      for item in old_slice:
        self._remove_item(item)
    list.__setslice__(self, i, j, new_items)
    for item in new_items:
      self._add_item(item)
    self.on_change()
  def __delitem__(self, key):
    self._remove_item(list.__getitem__(self, key))
    list.__delitem__(self, key)
    self.on_change()
  def __delslice__(self, i, j):
    old_slice = list.__getslice__(self, i, j)
    if (old_slice):
      for item in old_slice:
        self._remove_item(item)
    list.__delslice__(self, i, j)
    self.on_change()
  def append(self, item):
    list.append(self, item)
    self._add_item(item)
    self.on_change()
  def pop(self, i=None):
    if (i == None):
      item = list.pop(self)
    else:
      item = list.pop(self, i)
    self._remove_item(item)
    self.on_change()
    return(item)
  def extend (self, new_items):
    for item in new_items:
      self._add_item(item)
    list.extend(self, new_items)
    self.on_change()
  def insert (self, i, item):
    list.insert(self, i, item)
    self._add_item(item)
    self.on_change()
  def remove(self, item):
    list.remove(self, item)
    self._remove_item(item)
    self.on_change()
  def reverse(self):
    list.reverse(self)
    self.on_change()
  def sort(self, cmp=None):
    if (cmp == None):
      list.sort(self)
    else:
      list.sort(self, cmp=cmp)
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

# make an observable list that exposes the members of another list 
#  after passing them through a series of filtering functions
class FilteredList(Observable, list):
  # the class must be initialized with a source list whose contents to filter
  def __init__(self, source, filters=()):
    list.__init__(self)
    self._source = source
    self._source.add_observer(self.update)
    self._filters = filters
  # make this hashable so it can receive callbacks
  def __hash__(self):
    return(id(self))
  # expose the source list as a read-only property
  @property
  def source(self):
    return(self._source)
  # expose the list of filters as a property, which can be set to a tuple
  #  containing a series of filter functions, each of which accepts a sequence
  #  and returns a filtered sequence
  @property
  def filters(self):
    return(self._filters)
  @filters.setter
  def filters(self, sequence):
    self._filters = tuple(sequence)
    self.update()
  # update the contents of the list based on changes 
  #  to the source list or filters
  def update(self):
    # apply filters
    contents = self._source
    for func in self._filters:
      contents = func(contents)
    # replace contents and report a change
    self[0:] = contents
    self.on_change()

# make an object that exposes observable attributes for another object
class AttributeProxy(Observable, object):
  def __init__(self, target, from_name=None, to_name=None):
    self._target = target
    self._attribute_map = dict()
    self.proxy_attribute(from_name, to_name)
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
  def test_double_listener(self):
    self.obj.add_observer(self.on_change)
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
  def test_double_listener(self):
    self.list.add_observer(self.on_change)
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

class TestFilteredList(unittest.TestCase):
  def setUp(self):
    self.itemA = Object()
    self.itemB = Object()
    self.list = List()
    self.flist = FilteredList(self.list)
    self.changes = 0
  def on_change(self):
    self.changes += 1
  def test_unfiltered(self):
    self.flist.add_observer(self.on_change)
    self.list.append(self.itemA)
    self.assertEqual(self.changes, 1)
    self.assertIn(self.itemA, self.flist)
    self.itemA.on_change()
    self.assertEqual(self.changes, 2)
  def test_filtered(self):
    self.flist.add_observer(self.on_change)
    self.flist.filters = [ lambda s: (s[:-1]) ]
    self.assertEqual(self.changes, 1)
    self.list.extend((self.itemA, self.itemB))
    self.assertEqual(self.changes, 2)
    self.assertIn(self.itemA, self.flist)
    self.assertNotIn(self.itemB, self.flist)
    self.itemA.on_change()
    self.assertEqual(self.changes, 3)
    self.itemB.on_change()
    self.assertEqual(self.changes, 4)
    self.list.remove(self.itemB)
    self.assertNotIn(self.itemA, self.flist)
    self.assertNotIn(self.itemB, self.flist)
    self.assertEqual(self.changes, 5)

# run tests if this script is invoked by itself
if __name__ == '__main__':
  unittest.main()
