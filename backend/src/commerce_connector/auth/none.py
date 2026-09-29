from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("none")
class NoneAuth(AuthProvider):
    async def apply(self, request):
        return request
