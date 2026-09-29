import base64, hashlib, hmac, secrets, time
from urllib.parse import quote, urlsplit
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

def q(value):
    return quote(str(value), safe="~-._")

@auth_registry.decorator("oauth1")
class OAuth1Auth(AuthProvider):
    async def apply(self, request):
        data = self.config.model_dump()
        oauth = {
            "oauth_consumer_key": data.get("consumer_key",""),
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": data.get("signature_method","HMAC-SHA1"),
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": "1.0",
        }
        if data.get("oauth_token"):
            oauth["oauth_token"] = data["oauth_token"]
        pairs = [(q(k), q(v)) for k, v in {**request.params, **oauth}.items() if v is not None]
        pairs.sort()
        normalized = "&".join(f"{k}={v}" for k,v in pairs)
        parts = urlsplit(request.url)
        base_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
        base_string = "&".join([request.method.upper(), q(base_url), q(normalized)])
        signing_key = f"{q(data.get('consumer_secret',''))}&{q(data.get('oauth_token_secret',''))}".encode()
        digest = hashlib.sha256 if data.get("signature_method") == "HMAC-SHA256" else hashlib.sha1
        signature = base64.b64encode(hmac.new(signing_key, base_string.encode(), digest).digest()).decode()
        oauth["oauth_signature"] = signature
        request.headers["Authorization"] = "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k,v in sorted(oauth.items()))
        return request
