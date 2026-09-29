class WebhookRegistry:
    def __init__(self):self.handlers={}
    def register(self,event,handler):self.handlers[event]=handler
