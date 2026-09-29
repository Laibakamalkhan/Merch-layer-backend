import base64, hashlib, hmac, json, time
from urllib.parse import urlsplit
from commerce_connector.core.registry import auth_registry
from .base import AuthProvider

@auth_registry.decorator("hmac")
class HmacAuth(AuthProvider):
    async def apply(self, request):
        data = self.config.model_dump()
        timestamp = str(int(time.time()))
        parts = urlsplit(request.url)
        body = (
            json.dumps(request.json_body, separators=(",",":"), default=str).encode()
            if request.json_body is not None
            else request.content.encode() if isinstance(request.content,str)
            else (request.content or b"")
        )
        values = {
            "method": request.method.upper(),
            "url": request.url,
            "host": parts.netloc,
            "path": parts.path or "/",
            "timestamp": timestamp,
            "body_sha256": hashlib.sha256(body).hexdigest(),
        }
        canonical = str(data.get("hmac_template","{method}\n{path}\n{timestamp}")).format(**values)
        digest = hashlib.sha512 if data.get("hmac_algorithm") == "sha512" else hashlib.sha256
        raw = hmac.new(str(data.get("hmac_secret","")).encode(), canonical.encode(), digest).digest()
        signature = base64.b64encode(raw).decode() if data.get("signature_encoding") == "base64" else raw.hex()
        request.headers[data.get("hmac_header","X-Signature")] = signature
        ts_header = data.get("timestamp_header","X-Timestamp")
        if ts_header:
            request.headers[ts_header] = timestamp
        return request
