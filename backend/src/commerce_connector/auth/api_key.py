from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("api_key")
class ApiKeyAuth(AuthProvider):
    async def apply(self, request):
        data = self.config.model_dump()
        name = data.get("api_key_name", "X-API-Key")
        value = data.get("api_key", "")
        if data.get("api_key_location", "header") == "query":
            request.params[name] = value
        else:
            request.headers[name] = value
        return request
