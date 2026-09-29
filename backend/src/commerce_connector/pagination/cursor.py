from commerce_connector.core.registry import pagination_registry
from .graphql_cursor import GraphQLCursorPagination
@pagination_registry.decorator("cursor")
class CursorPagination(GraphQLCursorPagination):
    pass
