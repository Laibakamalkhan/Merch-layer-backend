from commerce_connector.core.registry import protocol_registry
from .rest import RestProtocol

@protocol_registry.decorator("bulk")
class BulkProtocol(RestProtocol):
    pass
