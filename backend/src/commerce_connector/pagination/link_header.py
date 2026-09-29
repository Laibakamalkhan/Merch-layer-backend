from commerce_connector.core.models import PaginationDecision
from commerce_connector.core.registry import pagination_registry
from .base import PaginationStrategy
@pagination_registry.decorator("link_header")
class LinkHeaderPagination(PaginationStrategy):
    def initial_state(self): return {"next_url":None}
    def prepare(self, request, state):
        if state.get("next_url"):
            request.url = state["next_url"]; request.params = {}
        return request
    def advance(self, response, records, state):
        link = response.headers.get("link")
        if not link: return PaginationDecision(False,state)
        rel_name = self.data.get("link_rel","next")
        for part in link.split(","):
            section = part.strip()
            if ";" not in section: continue
            url_part,*attrs = section.split(";")
            rel = None
            for attr in attrs:
                key,_,value = attr.strip().partition("=")
                if key == "rel": rel = value.strip().strip('"')
            if rel == rel_name:
                next_url = url_part.strip()
                if next_url.startswith("<") and next_url.endswith(">"):
                    next_url = next_url[1:-1]
                return PaginationDecision(True, {"next_url":next_url})
        return PaginationDecision(False,state)
