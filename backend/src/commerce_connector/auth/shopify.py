"""Shopify authentication - purana token aur naya Dev Dashboard (client credentials) dono.

Shopify ne 1 Jan 2026 se naye custom apps ke liye permanent `shpat_...` token dena band kar diya.
Ab Dev Dashboard app se Client ID + Client Secret milta hai, jinhe exchange karke 24 ghante ka
Admin API token banta hai. Yeh provider dono tareeqe sambhalta hai:

  1) auth.token          -> purani (legacy) app ka static shpat_ token, seedha use hota hai
  2) auth.client_id/secret -> Shopify se token exchange, cache hota hai aur expire hone se pehle refresh
"""
import time
from urllib.parse import urlsplit

from commerce_connector.core.exceptions import AuthenticationError
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider


@auth_registry.decorator("shopify_token")
class ShopifyTokenAuth(AuthProvider):
    def __init__(self, config, client):
        super().__init__(config, client)
        self._token = None
        self._expires_at = 0.0

    async def invalidate(self):
        # Sirf exchange kiya hua token dobara mangwana hai; static token ko chhedna nahi.
        self._token = None
        self._expires_at = 0.0

    async def _exchange(self, request, client_id: str, client_secret: str) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        parts = urlsplit(request.url)
        token_url = f"{parts.scheme}://{parts.netloc}/admin/oauth/access_token"
        response = await self.client.post(
            token_url,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            raise AuthenticationError(f"Shopify token exchange failed: HTTP {response.status_code}: {response.text[:300]}")
        try:
            payload = response.json()
        except Exception as exc:
            raise AuthenticationError(f"Shopify token exchange: unreadable response: {response.text[:200]}") from exc
        token = payload.get("access_token")
        if not token:
            raise AuthenticationError(f"Shopify token exchange: access_token missing: {str(payload)[:200]}")
        self._token = str(token)
        self._expires_at = time.time() + int(payload.get("expires_in") or 86399)
        return self._token

    async def apply(self, request):
        data = self.config.model_dump()
        header = data.get("token_header") or "X-Shopify-Access-Token"
        static_token = str(data.get("token") or "").strip()
        client_id = str(data.get("client_id") or "").strip()
        client_secret = str(data.get("client_secret") or "").strip()

        if static_token:
            token = static_token
        elif client_id and client_secret:
            token = await self._exchange(request, client_id, client_secret)
        else:
            raise AuthenticationError(
                "Shopify credentials missing: Client ID + Client Secret (Dev Dashboard) ya purana Admin API access token dena zaroori hai"
            )
        request.headers[header] = token
        return request
