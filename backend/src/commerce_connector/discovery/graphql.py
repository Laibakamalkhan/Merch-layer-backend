from commerce_connector.core.enums import ProtocolType
from commerce_connector.core.exceptions import DiscoveryError
from commerce_connector.core.models import DiscoveryResult
from commerce_connector.discovery.resource_detector import detect_resources

INTROSPECTION_QUERY='''query UniversalConnectorIntrospection {
  __schema {
    queryType { fields { name description } }
    mutationType { fields { name description } }
  }
}'''

async def discover_graphql(client,url,headers=None):
    response=await client.post(
        url,headers={"Content-Type":"application/json",**(headers or {})},
        json={"query":INTROSPECTION_QUERY},
    )
    if response.status_code>=400: raise DiscoveryError(f"GraphQL introspection failed: HTTP {response.status_code}")
    payload=response.json()
    if payload.get("errors"): raise DiscoveryError(f"GraphQL introspection errors: {payload['errors']}")
    schema=(payload.get("data",{}).get("__schema"))
    if not schema: raise DiscoveryError("GraphQL schema is unavailable.")
    operations=[]
    for kind,key in (("query","queryType"),("mutation","mutationType")):
        block=schema.get(key) or {}
        for field in block.get("fields") or []:
            operations.append({"kind":kind,"name":field.get("name"),"description":field.get("description")})
    return DiscoveryResult(
        protocol=ProtocolType.GRAPHQL,platform=None,operations=operations,
        resources=detect_resources(operations),confidence=0.95,raw_schema=schema,
    )
