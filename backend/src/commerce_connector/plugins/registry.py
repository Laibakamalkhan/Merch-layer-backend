class PluginRegistry:
    def __init__(self):self.plugins={}
    def register(self,plugin):self.plugins[plugin.name]=plugin
