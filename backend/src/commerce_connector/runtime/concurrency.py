import asyncio
def semaphore(limit): return asyncio.Semaphore(limit)
