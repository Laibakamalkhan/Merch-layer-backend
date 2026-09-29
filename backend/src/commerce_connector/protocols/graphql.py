from copy import deepcopy
from commerce_connector.core.models import RequestSpec
from commerce_connector.core.registry import protocol_registry
from commerce_connector.utils.urls import join_url
from .base import ProtocolDriver

@protocol_registry.decorator("graphql")
class GraphQLProtocol(ProtocolDriver):
    def build_request(self, manifest, resource, variables=None):
        variables = variables or {}
        gql_variables = deepcopy(resource.graphql_variables)
        gql_variables.update(variables.get("graphql_variables", {}))
        return RequestSpec(
            method=resource.method.upper() or "POST",
            url=join_url(manifest.base_url, resource.path),
            headers={"Content-Type": "application/json", **manifest.default_headers, **resource.headers, **variables.get("headers", {})},
            params={**manifest.default_params, **resource.params},
            json_body={"query": resource.graphql_query, "variables": gql_variables},
        )
