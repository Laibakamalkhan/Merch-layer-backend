from copy import deepcopy
from commerce_connector.core.models import RequestSpec
from commerce_connector.core.registry import protocol_registry
from commerce_connector.utils.urls import join_url
from .base import ProtocolDriver

@protocol_registry.decorator("rest")
class RestProtocol(ProtocolDriver):
    def build_request(self, manifest, resource, variables=None):
        variables = variables or {}
        return RequestSpec(
            method=resource.method.upper(),
            url=join_url(manifest.base_url, resource.path),
            headers={**manifest.default_headers, **resource.headers, **variables.get("headers", {})},
            params={**manifest.default_params, **resource.params, **variables.get("params", {})},
            json_body=deepcopy(variables.get("body", resource.body)),
        )
