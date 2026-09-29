from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from .base import PaginationStrategy
@pagination_registry.decorator("none")
class NoPagination(PaginationStrategy):
    def initial_state(self): return {}
    def prepare(self, request, state): return request
    def advance(self, response, records, state): return PaginationDecision(False, state)
