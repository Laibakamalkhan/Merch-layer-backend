from abc import abstractmethod
from .base import AuthProvider
class SignedRequestAuth(AuthProvider):
    @abstractmethod
    async def apply(self, request):
        raise NotImplementedError
