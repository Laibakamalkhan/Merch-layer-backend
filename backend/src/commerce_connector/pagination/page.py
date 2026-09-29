from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from .base import PaginationStrategy
@pagination_registry.decorator("page")
class PagePagination(PaginationStrategy):
    def initial_state(self): return {"page": int(self.data.get("start_page",1))}
    def prepare(self, request, state):
        request.params[self.data.get("page_param","page")] = state["page"]
        if self.data.get("page_size") and self.data.get("page_size_param"):
            request.params[self.data["page_size_param"]] = self.data["page_size"]
        return request
    def advance(self, response, records, state):
        if self.config.stop_on_empty and isinstance(records,list) and not records:
            return PaginationDecision(False,state)
        size = self.data.get("page_size")
        if size and isinstance(records,list) and len(records) < int(size):
            return PaginationDecision(False,state)
        return PaginationDecision(True, {"page": int(state["page"])+1})
