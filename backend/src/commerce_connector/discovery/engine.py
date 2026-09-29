import httpx
from commerce_connector.discovery.graphql import discover_graphql
from commerce_connector.discovery.openapi import discover_openapi
from commerce_connector.discovery.platform_detector import detect_platform
from commerce_connector.discovery.protocol_detector import candidate_discovery_urls
from commerce_connector.security.url_policy import URLPolicy

class DiscoveryEngine:
    def __init__(self,allow_private_networks=False):
        self.policy=URLPolicy(allow_private_networks)
    async def discover(self,base_url,headers=None):
        self.policy.validate(base_url)
        platform,platform_confidence=detect_platform(base_url)
        candidates=candidate_discovery_urls(base_url)
        async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
            for url in candidates["openapi"]:
                try:
                    result=await discover_openapi(client,url)
                    result.platform=platform
                    result.confidence=max(result.confidence,platform_confidence)
                    return result
                except Exception:pass
            for url in candidates["graphql"]:
                try:
                    result=await discover_graphql(client,url,headers=headers)
                    result.platform=platform
                    result.confidence=max(result.confidence,platform_confidence)
                    return result
                except Exception:pass
        return None
