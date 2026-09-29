import httpx
from commerce_connector.manifests.schema import ResponseSpecConfig
from commerce_connector.response.parser import parse_response
def test_json_parser():
    req=httpx.Request("GET","https://example.com")
    response=httpx.Response(200,request=req,json={"items":[{"id":1}]},headers={"Content-Type":"application/json"})
    parsed=parse_response(response,ResponseSpecConfig(format="json"))
    assert parsed.data["items"][0]["id"]==1
