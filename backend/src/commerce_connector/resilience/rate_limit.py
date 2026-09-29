import asyncio, time
class TokenBucketLimiter:
    def __init__(self, requests_per_second, burst=1):
        self.rate = requests_per_second
        self.capacity = float(max(1,burst))
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
    async def acquire(self):
        if not self.rate: return
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now-self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed*self.rate)
                self.last_refill = now
                if self.tokens >= 1:
                    self.tokens -= 1; return
                wait = (1-self.tokens)/self.rate
            await asyncio.sleep(wait)
