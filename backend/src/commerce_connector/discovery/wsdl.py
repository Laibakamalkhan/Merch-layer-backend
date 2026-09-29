from commerce_connector.core.enums import ProtocolType
from commerce_connector.core.models import DiscoveryResult
async def discover_wsdl(client,url):
    response=await client.get(url); response.raise_for_status()
    text=response.text; operations=[]; marker='operation name="'
    for segment in text.split(marker)[1:]:
        name=segment.split('"',1)[0]
        if name:operations.append({"kind":"operation","name":name})
    return DiscoveryResult(
        protocol=ProtocolType.SOAP,platform=None,operations=operations,
        resources=[],confidence=0.7,raw_schema=text,
    )
