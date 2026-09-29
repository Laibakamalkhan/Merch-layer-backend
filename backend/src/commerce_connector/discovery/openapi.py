import yaml
from commerce_connector.core.enums import ProtocolType
from commerce_connector.core.exceptions import DiscoveryError
from commerce_connector.core.models import DiscoveryResult
from commerce_connector.discovery.resource_detector import detect_resources

async def discover_openapi(client,url):
    response=await client.get(url)
    if response.status_code>=400: raise DiscoveryError(f"OpenAPI discovery failed: HTTP {response.status_code}")
    try:
        try:schema=response.json()
        except Exception:schema=yaml.safe_load(response.text)
    except Exception as exc: raise DiscoveryError("Unable to parse OpenAPI document.") from exc
    operations=[]
    for path,methods in (schema.get("paths") or {}).items():
        for method,operation in (methods or {}).items():
            if method.lower() not in {"get","post","put","patch","delete"}:continue
            operations.append({
                "operation_id":operation.get("operationId"),
                "method":method.upper(),
                "path":path,
                "summary":operation.get("summary"),
            })
    return DiscoveryResult(
        protocol=ProtocolType.REST,platform=None,operations=operations,
        resources=detect_resources(operations),confidence=0.95,raw_schema=schema,
    )
