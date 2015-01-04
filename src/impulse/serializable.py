import yaml

_classes = set()
def add(cls):
  global _classes
  if (cls in _classes): return
  _classes.add(cls)
  # set the class up to be saved to YAML
  tag = u'!%s' % cls.__name__
  def representer(dumper, instance):
    return(dumper.represent_mapping(tag, cls.serialize(instance)))
  def constructor(loader, node):
    kwargs = loader.construct_mapping(node, deep=True)
    return(cls(**kwargs))
  yaml.add_representer(cls, representer)
  yaml.add_constructor(tag, constructor)
  # set the class up to be pickled and unpickled
  def getstate(self):
    return(self.serialize())
  def setstate(self, d):
    self.__init__(**d)
  cls.__getstate__ = getstate
  cls.__setstate__ = setstate
    
