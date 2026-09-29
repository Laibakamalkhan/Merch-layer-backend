from urllib.parse import urljoin
from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from commerce_connector.utils.paths import get_path
from .base import PaginationStrategy
@pagination_registry.decorator("next_url")
class NextUrlPagination(PaginationStrategy):
    def initial_state(self): return {"next_url":None}
    def prepare(self, request, state):
        if state.get("next_url"):
            request.url = state["next_url"]; request.params = {}
        return request
    def advance(self, response, records, state):
        value = get_path(response.data, self.data.get("next_url_path"))
        if not value: return PaginationDecision(False,state)
        return PaginationDecision(True, {"next_url": urljoin(response.url,str(value))})
