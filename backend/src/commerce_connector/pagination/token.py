from commerce_connector.core.exceptions import PaginationError
from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from commerce_connector.utils.paths import get_path
from .base import PaginationStrategy
@pagination_registry.decorator("next_token")
class NextTokenPagination(PaginationStrategy):
    def initial_state(self): return {"token": None}
    def prepare(self, request, state):
        token = state.get("token")
        if token is None: return request
        name = self.data.get("token_param","next_token")
        loc = self.data.get("token_location","query")
        if loc == "query": request.params[name] = token
        elif loc == "header": request.headers[name] = str(token)
        elif loc == "body":
            if request.json_body is None: request.json_body = {}
            if not isinstance(request.json_body,dict): raise PaginationError("Body token pagination requires JSON object body")
            request.json_body[name] = token
        elif loc == "graphql_variable":
            if not isinstance(request.json_body,dict): raise PaginationError("GraphQL token pagination requires JSON body")
            request.json_body.setdefault("variables",{})[name] = token
        else: raise PaginationError(f"Unsupported token location: {loc}")
        return request
    def advance(self, response, records, state):
        token = get_path(response.data, self.data.get("next_token_path"))
        if token in (None,"",False): return PaginationDecision(False,state)
        return PaginationDecision(True, {"token":token})
