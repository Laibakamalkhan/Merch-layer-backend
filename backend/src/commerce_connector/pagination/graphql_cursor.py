from commerce_connector.core.exceptions import PaginationError
from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from commerce_connector.utils.paths import get_path
from .base import PaginationStrategy
@pagination_registry.decorator("graphql_cursor")
class GraphQLCursorPagination(PaginationStrategy):
    def initial_state(self): return {"cursor":None}
    def prepare(self, request, state):
        if not isinstance(request.json_body,dict):
            raise PaginationError("GraphQL cursor pagination requires JSON body")
        request.json_body.setdefault("variables",{})[self.data.get("cursor_variable","cursor")] = state.get("cursor")
        return request
    def advance(self, response, records, state):
        has_next = get_path(response.data, self.data.get("has_next_path"))
        cursor = get_path(response.data, self.data.get("cursor_path"))
        if not has_next or cursor in (None,""): return PaginationDecision(False,state)
        return PaginationDecision(True, {"cursor":cursor})
