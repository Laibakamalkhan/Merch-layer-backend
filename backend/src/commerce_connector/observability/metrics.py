from collections import Counter
class InMemoryMetrics:
    def __init__(self): self.counters=Counter()
    def inc(self,name,value=1): self.counters[name]+=value
    def snapshot(self): return dict(self.counters)
