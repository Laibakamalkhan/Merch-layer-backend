from commerce_connector.core.models import RequestSpec
from commerce_connector.core.registry import protocol_registry
from commerce_connector.utils.urls import join_url
from .base import ProtocolDriver

@protocol_registry.decorator("soap")
class SoapProtocol(ProtocolDriver):
    def build_request(self, manifest, resource, variables=None):
        variables = variables or {}
        xml = resource.xml_body or ""
        for key, value in variables.get("soap_variables", {}).items():
            xml = xml.replace("{{" + key + "}}", str(value))
        headers = {"Content-Type": resource.content_type or "text/xml; charset=utf-8", **manifest.default_headers, **resource.headers}
        if resource.soap_action:
            headers["SOAPAction"] = resource.soap_action
        return RequestSpec(
            method=resource.method.upper() or "POST",
            url=join_url(manifest.base_url, resource.path),
            headers=headers,
            params={**manifest.default_params, **resource.params},
            content=xml,
        )
