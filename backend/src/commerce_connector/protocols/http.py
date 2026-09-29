from commerce_connector.core.registry import protocol_registry
from .rest import RestProtocol

@protocol_registry.decorator("http")
class GenericHttpProtocol(RestProtocol):
    pass
