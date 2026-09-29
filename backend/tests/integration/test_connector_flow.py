import httpx,pytest
from commerce_connector.core.connector import UniversalCommerceConnector
from commerce_connector.manifests.schema import PlatformManifest

@pytest.mark.asyncio
async def test_rest_connector_flow():
    def handler(request):
        page=int(request.url.params.get("page",1))
        items=[{"id":1},{"id":2}] if page==1 else [{"id":3}]
        return httpx.Response(200,request=request,json={"items":items},headers={"Content-Type":"application/json"})
    manifest=PlatformManifest.model_validate({
        "id":"test","name":"Test","platform":"custom","protocol":"rest",
        "base_url":"https://example.test","auth":{"type":"none"},
        "resources":{"orders":{
            "path":"/orders",
            "response":{"format":"json","records_path":"items"},
            "pagination":{"type":"page","records_path":"items","page_param":"page","page_size_param":"limit","page_size":2}
        }}
    })
    connector=UniversalCommerceConnector(manifest,transport=httpx.MockTransport(handler),allow_private_networks=True)
    records=[]
    async with connector:
        async for page in connector.stream("orders"):
            records.extend(page.records)
    assert records==[{"id":1},{"id":2},{"id":3}]
