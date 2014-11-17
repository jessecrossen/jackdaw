import observable

# make a singleton for managing the selection
class SelectionSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self._models = set()
  @property
  def models(self):
    return(self._models)
  # add a model to the selection
  def select(self, model):
    # don't allow an item containing this one to remain selected
    containers = list()
    for item in self._models:
      if (item.contains_model(model)):
        containers.append(item)
    for container in containers:
      container.selected = False
    # deselect all descendents of the new item
    self.deselect_children(model)
    # select the model
    self._models.add(model)
    if (not model._selected):
      model._selected = True
      model.on_change()
  # remove a model from the selection
  def deselect(self, model):
    try:
      self._models.remove(model)
    except KeyError: pass
    if (model._selected):
      model._selected = False
      model.on_change()
  # deselect all selected models
  def deselect_all(self):
    models = set(self._models)
    for model in models:
      self.deselect(model)
  # remove all children of a model from the selection
  def deselect_children(self, model):
    if (isinstance(model, ModelList)):
      for child in model:
        child.selected = False
        self.deselect_children(child)
    elif (isinstance(model, Model)):
      for key in dir(model):
        # skip private stuff
        if (key[0] == '_'): continue
        value = getattr(model, key)
        try:
          value.selected = False
        except AttributeError: continue
        if (isinstance(value, ModelList)):
          self.deselect_children(value)
    
# make a global instance
Selection = SelectionSingleton()

# make a mixin to add selectability
class Selectable(object):
  def __init__(self):
    self._selected = False
  @property
  def selected(self):
    return(self._selected)
  @selected.setter
  def selected(self, value):
    if (value != self._selected):
      if (value):
        Selection.select(self)
      else:
        Selection.deselect(self)
      self.on_change()

# make a base class to implement common functions of the model layer
class Model(Selectable, observable.Object):
  def __init__(self):
    Selectable.__init__(self)
    observable.Object.__init__(self)
    # initialize cached data attributes  
    self.invalidate()
  # invalidate cached data when the model changes
  def on_change(self):
    self.invalidate()
    observable.Object.on_change(self)
  # override to invalidate cached data
  def invalidate(self):
    pass
  # return if the model contains the given model in one of its properties
  def contains_model(self, model, visited=None):
    if (visited is None):
      visited = set()
    if (self in visited): return
    visited.add(self)
    for key in dir(self):
      # skip private stuff
      if (key[0] == '_'): continue
      value = getattr(self, key)
      if (value is model):
        return(True)
      try:
        if (value.contains_model(model, visited)):
          return(True)
      except AttributeError: continue

# make a base class to implement common functions for lists of Model instances
class ModelList(Selectable, observable.List):
  def __init__ (self, value=()):
    Selectable.__init__(self)
    observable.List.__init__(self, value)
    # initialize cached data attributes  
    self.invalidate()
  # invalidate cached data when the model changes
  def on_change(self):
    self.invalidate()
    observable.Object.on_change(self)
  # override to invalidate cached data
  def invalidate(self):
    pass
  # return whether the list or one of its items contains the given model
  def contains_model(self, model, visited=None):
    if (visited is None):
      visited = set()
    if (self in visited): return
    visited.add(self)
    if (model in self):
      return(True)
    for item in self:
      try:
        if (item.contains_model(model)):
          return(True)
      except AttributeError: continue
    return(False)
