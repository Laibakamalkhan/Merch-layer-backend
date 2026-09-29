from commerce_connector.core.registry import protocol_registry
from .rest import RestProtocol

@protocol_registry.decorator("file")
class FileFeedProtocol(RestProtocol):
    """Remote HTTP file/feed transport. Local file access is intentionally excluded."""
    pass
