import base64
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("basic")
class BasicAuth(AuthProvider):
    async def apply(self, request):
        data = self.config.model_dump()
        raw = f"{data.get('username','')}:{data.get('password','')}".encode()
        request.headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
        return request
