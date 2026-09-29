async def submit_bulk_job(client,request_kwargs):
    return await client.request(**request_kwargs)
