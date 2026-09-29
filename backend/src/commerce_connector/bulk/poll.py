import asyncio
async def poll_until_ready(check,*,interval_seconds=2.0,max_attempts=300):
    for _ in range(max_attempts):
        result=await check()
        if result.get("ready"):return result
        await asyncio.sleep(interval_seconds)
    raise TimeoutError("Bulk job did not become ready.")
