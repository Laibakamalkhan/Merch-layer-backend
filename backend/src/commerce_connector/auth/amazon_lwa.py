import time
from commerce_connector.core.exceptions import AuthenticationError
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("amazon_lwa")
class AmazonLWAAuth(AuthProvider):
    def __init__(self, config, client):
        super().__init__(config, client)
        self._token = None
        self._expires_at = 0.0

    async def invalidate(self):
        self._token = None
        self._expires_at = 0.0

    async def apply(self, request):
        data = self.config.model_dump()
        if not self._token or time.time() >= self._expires_at - 30:
            form = {
                "grant_type": "refresh_token",
                "refresh_token": data.get("lwa_refresh_token",""),
                "client_id": data.get("lwa_client_id",""),
                "client_secret": data.get("lwa_client_secret",""),
            }
            response = await self.client.post(
                data.get("token_url", "https://api.amazon.com/auth/o2/token"),
                data=form,
            )
            if response.status_code >= 400:
                raise AuthenticationError(f"Amazon LWA failed: HTTP {response.status_code}")
            payload = response.json()
            self._token = payload.get("access_token")
            if not self._token:
                raise AuthenticationError("Amazon LWA response missing access_token")
            self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        request.headers[data.get("amazon_access_token_header","x-amz-access-token")] = self._token
        return request
