async def download_file(client,url):
    response=await client.get(url); response.raise_for_status(); return response.content
