import time, httpx
from commerce_connector.core.exceptions import AuthenticationError
from commerce_connector.core.registry import auth_registry
from commerce_connector.utils.paths import get_path
from .base import AuthProvider

class OAuth2Base(AuthProvider):
    def __init__(self, config, client):
        super().__init__(config, client)
        self._token = None
        self._expires_at = 0.0

    async def invalidate(self):
        self._token = None
        self._expires_at = 0.0

    async def fetch_token(self, form):
        data = self.config.model_dump()
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        if data.get("scope"):
            form["scope"] = data["scope"]
        form.update(data.get("oauth_extra") or {})
        response = await self.client.post(
            data["token_url"],
            data=form,
            auth=httpx.BasicAuth(data.get("client_id",""), data.get("client_secret","")),
        )
        if response.status_code >= 400:
            raise AuthenticationError(f"OAuth2 token request failed: HTTP {response.status_code}")
        payload = response.json()
        path = data.get("token_response_path", "access_token")
        token = get_path(payload, path)
        if not token:
            raise AuthenticationError(f"OAuth2 response missing {path}")
        self._token = str(token)
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._token

@auth_registry.decorator("oauth2_client_credentials")
class OAuth2ClientCredentialsAuth(OAuth2Base):
    async def apply(self, request):
        token = await self.fetch_token({"grant_type": "client_credentials"})
        request.headers["Authorization"] = f"Bearer {token}"
        return request

@auth_registry.decorator("oauth2_refresh_token")
class OAuth2RefreshTokenAuth(OAuth2Base):
    async def apply(self, request):
        data = self.config.model_dump()
        token = await self.fetch_token({"grant_type": "refresh_token", "refresh_token": data.get("refresh_token","")})
        request.headers["Authorization"] = f"Bearer {token}"
        return request
