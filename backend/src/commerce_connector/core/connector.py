from pathlib import Path
import httpx

from commerce_connector.auth import amazon_lwa, api_key, basic, bearer, custom, hmac, none, oauth1, oauth2, shopify
from commerce_connector.pagination import cursor, graphql_cursor, link_header, next_url, none as pagination_none, offset, page, token
from commerce_connector.protocols import bulk, file, graphql, http, rest, soap
from commerce_connector.core.models import ConnectorPage
from commerce_connector.core.registry import auth_registry, pagination_registry, protocol_registry
from commerce_connector.manifests.compiler import compile_manifest
from commerce_connector.manifests.schema import PlatformManifest
from commerce_connector.response.extractor import extract_records
from commerce_connector.response.parser import parse_response
from commerce_connector.security.url_policy import URLPolicy
from commerce_connector.transport.client import ResilientHttpClient
from commerce_connector.utils.helpers import count_records

class UniversalCommerceConnector:
    def __init__(self, manifest, *, timeout_seconds=60.0, transport=None, allow_private_networks=False):
        self.manifest = manifest if isinstance(manifest,PlatformManifest) else compile_manifest(manifest)
        self.timeout_seconds=timeout_seconds
        self.transport=transport
        self.url_policy=URLPolicy(allow_private_networks)
        self._transport=None
        self._auth=None

    async def __aenter__(self):
        await self.open(); return self
    async def __aexit__(self,exc_type,exc,tb):
        await self.close()

    async def open(self):
        if self._transport is not None:return
        self.url_policy.validate(self.manifest.base_url)
        self._transport=ResilientHttpClient(self.manifest,timeout_seconds=self.timeout_seconds,transport=self.transport)
        auth_cls=auth_registry.get(self.manifest.auth.type)
        self._auth=auth_cls(self.manifest.auth,self._transport.client)

    async def close(self):
        if self._transport is not None: await self._transport.close()
        self._transport=None; self._auth=None

    def resources(self):
        return sorted(self.manifest.resources.keys())

    async def test_connection(self, resource=None):
        target=resource or self.resources()[0]
        async for page in self.stream(target,max_pages=1):
            return {"ok":True,"resource":target,"status_code":page.response.status_code,"url":page.response.url,"records":page.record_count}
        return {"ok":False,"resource":target}

    async def stream(self, resource_name, *, variables=None, resume_state=None, max_pages=None):
        await self.open()
        resource=self.manifest.resources[resource_name]
        protocol=resource.protocol or self.manifest.protocol
        driver=protocol_registry.get(protocol.value)()
        paginator=pagination_registry.get(resource.pagination.type)(resource.pagination)
        state=dict(resume_state) if resume_state is not None else paginator.initial_state()
        limit=resource.pagination.max_pages
        if max_pages is not None: limit=min(limit,max_pages)
        for page_number in range(1,limit+1):
            request=driver.build_request(self.manifest,resource,variables)
            request=paginator.prepare(request,state)
            request=await self._auth.apply(request)
            self.url_policy.validate(request.url)
            raw_response=await self._transport.send(request,self._auth)
            response=parse_response(raw_response,resource.response)
            records=extract_records(response,resource.response,resource.pagination.records_path)
            decision=paginator.advance(response,records,state)
            yield ConnectorPage(
                resource=resource_name,page_number=page_number,request=request,response=response,
                records=records,record_count=count_records(records),
                checkpoint=decision.state if decision.has_next else None,
            )
            if not decision.has_next: break
            state=decision.state
