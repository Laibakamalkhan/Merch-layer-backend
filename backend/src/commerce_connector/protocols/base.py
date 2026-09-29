from abc import ABC, abstractmethod
from commerce_connector.core.models import RequestSpec

class ProtocolDriver(ABC):
    @abstractmethod
    def build_request(self, manifest, resource, variables=None) -> RequestSpec:
        raise NotImplementedError
