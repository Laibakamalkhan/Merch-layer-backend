import importlib
from commerce_connector.core.exceptions import AuthenticationError
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("custom")
class CustomAuth(AuthProvider):
    async def apply(self, request):
        path = self.config.model_dump().get("plugin")
        if not path or ":" not in path:
            raise AuthenticationError("custom auth requires plugin='package.module:ClassName'")
        module_name, class_name = path.split(":",1)
        cls = getattr(importlib.import_module(module_name), class_name)
        if not issubclass(cls, AuthProvider):
            raise AuthenticationError(f"{path} is not an AuthProvider")
        return await cls(self.config, self.client).apply(request)
