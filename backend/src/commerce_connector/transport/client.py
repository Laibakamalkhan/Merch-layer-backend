import asyncio
from urllib.parse import urlsplit
import httpx
from commerce_connector.core.exceptions import ProtocolError
from commerce_connector.resilience.backoff import retry_delay
from commerce_connector.resilience.circuit_breaker import CircuitBreaker
from commerce_connector.resilience.rate_limit import TokenBucketLimiter

class ResilientHttpClient:
    def __init__(self, manifest, timeout_seconds=60.0, transport=None):
        self.manifest = manifest
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=True, transport=transport)
        self.limiter = TokenBucketLimiter(manifest.rate_limit.requests_per_second, manifest.rate_limit.burst)
        self.breaker = CircuitBreaker(
            manifest.circuit_breaker.enabled,
            manifest.circuit_breaker.failure_threshold,
            manifest.circuit_breaker.recovery_timeout_seconds,
        )
    async def close(self):
        await self.client.aclose()
    async def send(self, request, auth_provider):
        retry = self.manifest.retry
        host = urlsplit(request.url).netloc
        last_response = None
        last_error = None
        for attempt in range(retry.max_attempts):
            self.breaker.before_request(host)
            await self.limiter.acquire()
            try:
                response = await self.client.request(
                    request.method, request.url,
                    headers=request.headers, params=request.params,
                    json=request.json_body, content=request.content,
                )
                last_response = response
                if 200 <= response.status_code < 400:
                    self.breaker.success(host)
                    return response
                if response.status_code in {401,403} and attempt+1 < retry.max_attempts:
                    await auth_provider.invalidate()
                    request = await auth_provider.apply(request)
                if response.status_code not in retry.retry_statuses and response.status_code not in {401,403}:
                    self.breaker.failure(host)
                    response.raise_for_status()
                self.breaker.failure(host)
            except (httpx.ConnectError,httpx.ReadTimeout,httpx.WriteTimeout,httpx.PoolTimeout,httpx.RemoteProtocolError) as exc:
                last_error = exc
                self.breaker.failure(host)
            if attempt+1 >= retry.max_attempts:
                break
            await asyncio.sleep(retry_delay(
                last_response, attempt, retry.base_delay_seconds, retry.max_delay_seconds,
                self.manifest.rate_limit.respect_retry_after,
            ))
        if last_response is not None:
            raise ProtocolError(f"Upstream HTTP {last_response.status_code}: {last_response.text[:1000]}")
        raise ProtocolError(f"Request failed after retries: {last_error}")
