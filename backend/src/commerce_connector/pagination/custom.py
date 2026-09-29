from commerce_connector.core.exceptions import PaginationError
from .base import PaginationStrategy
class CustomPagination(PaginationStrategy):
    def initial_state(self): raise PaginationError("Custom pagination must be supplied by a plugin.")
    def prepare(self,request,state): raise PaginationError("Custom pagination must be supplied by a plugin.")
    def advance(self,response,records,state): raise PaginationError("Custom pagination must be supplied by a plugin.")
