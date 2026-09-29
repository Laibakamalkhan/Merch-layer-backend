from commerce_connector.core.exceptions import PaginationError
from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from .base import PaginationStrategy
@pagination_registry.decorator("offset")
class OffsetPagination(PaginationStrategy):
    def initial_state(self): return {"offset": int(self.data.get("start_offset",0))}
    def prepare(self, request, state):
        request.params[self.data.get("offset_param","offset")] = state["offset"]
        if self.data.get("page_size"):
            request.params[self.data.get("limit_param","limit")] = self.data["page_size"]
        return request
    def advance(self, response, records, state):
        size = self.data.get("page_size")
        if isinstance(records,list):
            if self.config.stop_on_empty and not records:
                return PaginationDecision(False,state)
            if size and len(records) < int(size):
                return PaginationDecision(False,state)
            step = int(size or len(records))
        else:
            if not size: raise PaginationError("offset pagination requires page_size")
            step = int(size)
        return PaginationDecision(True, {"offset": int(state["offset"])+step})
