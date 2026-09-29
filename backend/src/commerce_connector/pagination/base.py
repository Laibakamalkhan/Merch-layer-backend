from abc import ABC, abstractmethod

class PaginationStrategy(ABC):
    def __init__(self, config):
        self.config = config
        self.data = config.model_dump()
    @abstractmethod
    def initial_state(self): ...
    @abstractmethod
    def prepare(self, request, state): ...
    @abstractmethod
    def advance(self, response, records, state): ...
