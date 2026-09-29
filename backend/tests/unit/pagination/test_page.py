from commerce_connector.manifests.schema import PaginationSpec
from commerce_connector.pagination.page import PagePagination
from commerce_connector.core.models import RequestSpec,ResponseSpec
def test_page_pagination():
    strategy=PagePagination(PaginationSpec.model_validate({
        "type":"page","page_param":"page","page_size_param":"limit","page_size":2
    }))
    state=strategy.initial_state()
    request=strategy.prepare(RequestSpec(method="GET",url="https://example.com"),state)
    assert request.params["page"]==1 and request.params["limit"]==2
    decision=strategy.advance(
        ResponseSpec(status_code=200,url="https://example.com",headers={},data={},raw_bytes=b""),
        [{"id":1},{"id":2}],state,
    )
    assert decision.has_next and decision.state["page"]==2
