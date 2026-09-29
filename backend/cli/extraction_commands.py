from commerce_connector.runtime.multi_connection import execute_connections
async def extract(connections,*,max_concurrency=5):
    return await execute_connections(connections,max_concurrency=max_concurrency)
