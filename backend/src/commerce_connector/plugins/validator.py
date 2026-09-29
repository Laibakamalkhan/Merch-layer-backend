def validate_plugin_class(cls):
    if not isinstance(cls,type): raise TypeError("Plugin must be a class.")
