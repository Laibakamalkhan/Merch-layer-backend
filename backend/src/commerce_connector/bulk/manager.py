from .download import download_file
from .poll import poll_until_ready
class BulkManager:
    def __init__(self,client):self.client=client
    async def run(self,submit,check,get_download_url):
        await submit(); state=await poll_until_ready(check); return await download_file(self.client,get_download_url(state))
