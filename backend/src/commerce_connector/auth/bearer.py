from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("bearer")
class BearerAuth(AuthProvider):
    async def apply(self, request):
        data = self.config.model_dump()
        header = data.get("token_header", "Authorization")
        prefix = data.get("token_prefix", "Bearer")
        token = data.get("token", "")
        request.headers[header] = f"{prefix} {token}".strip() if prefix else str(token)
        return request
