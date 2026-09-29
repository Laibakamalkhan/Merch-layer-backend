class PluginPolicy:
    def __init__(self,allow_dynamic_plugins=False):self.allow_dynamic_plugins=allow_dynamic_plugins
    def assert_allowed(self):
        if not self.allow_dynamic_plugins: raise PermissionError("Dynamic plugins are disabled by policy.")
