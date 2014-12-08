import observable

# make a singleton for managing the selection
class SelectionSingleton(observable.Object):
  def __init__(self):
    observable.Object.__init__(self)
    self._models = set()
  @property
  def models(self):
    return(self._models)
  @models.setter
  def models(self, models):
    models = set(models)
    old_models = self._models.difference(models)
    new_models = models.difference(self._models)
    self._models = models
    for model in old_models:
      if (model._selected):
        model._selected = False
        model.on_change()
    for model in new_models:
      if (not model._selected):
        model._selected = True
        model.on_change()
    if ((len(old_models) > 0) or (len(new_models) > 0)):
      self.on_change()
  # add a model to the selection
  def select(self, model):
    # don't allow an item containing this one to remain selected
    containers = list()
    for item in self._models:
      if (item.contains_model(model)):
        containers.append(item)
    for container in containers:
      container.selected = False
    # deselect all descendents of the new item, if anything else is selected
    if (len(self._models) > 0):
      self.deselect_children(model)
    # select the model
    self._models.add(model)
    if (not model._selected):
      model._selected = True
      model.on_change()
      self.on_change()
  # remove a model from the selection
  def deselect(self, model):
    try:
      self._models.remove(model)
    except KeyError: pass
    if (model._selected):
      model._selected = False
      model.on_change()
      self.on_change()
  # deselect all selected models
  def deselect_all(self):
    models = set(self._models)
    for model in models:
      if (model._selected):
        model._selected = False
        model.on_change()
    self._models = set()
    if (len(models) > 0):
      self.on_change()
  # remove all children of a model from the selection
  def deselect_children(self, model):
    for item in set(self._models):
      if (model.contains_model(item)):
        try:
          item.selected = False
        except AttributeError: continue
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
  # override to return a list of attribute values that point to 
  #  models or model lists, used to optimize walking the model tree
  @property
  def model_refs(self):
    return()
  # return if the model contains the given model in one of its properties
  def contains_model(self, model, visited=None):
    if (visited is None):
      visited = set()
    if (self in visited): return
    visited.add(self)
    for ref in self.model_refs:
      if (ref is model):
        return(True)
      try:
        if (ref.contains_model(model, visited)):
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
  # override to return a list of attribute values that point to 
  #  models or model lists, used to optimize walking the model tree
  @property
  def model_refs(self):
    return()
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
