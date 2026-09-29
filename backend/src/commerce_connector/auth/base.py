from abc import ABC, abstractmethod

class AuthProvider(ABC):
    def __init__(self, config, client):
        self.config = config
        self.client = client

    @abstractmethod
    async def apply(self, request):
        raise NotImplementedError

    async def invalidate(self):
        return None
