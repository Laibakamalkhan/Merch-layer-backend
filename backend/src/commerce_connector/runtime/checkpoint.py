class CheckpointStore:
    def __init__(self): self.values={}
    def save(self,connection_id,resource,state): self.values[(connection_id,resource)] = dict(state)
    def get(self,connection_id,resource): return self.values.get((connection_id,resource))
