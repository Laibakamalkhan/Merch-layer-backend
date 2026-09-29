import asyncio
from .executor import execute_connection

async def execute_connections(connections, *, max_concurrency=5, allow_private_networks=False):
    limiter=asyncio.Semaphore(max_concurrency)
    async def run_one(connection):
        async with limiter:
            return await execute_connection(connection,allow_private_networks=allow_private_networks)
    return await asyncio.gather(*[
        asyncio.create_task(run_one(connection))
        for connection in connections
    ])
