import yaml

# add serialization for the given class
def add(cls):
  tag = u'!%s' % cls.__name__
  def representer(dumper, instance):
    return(dumper.represent_mapping(tag, cls.serialize(instance)))
  def constructor(loader, node):
    kwargs = loader.construct_mapping(node, deep=True)
    return(cls(**kwargs))
  yaml.add_representer(cls, representer)
  yaml.add_constructor(tag, constructor)
