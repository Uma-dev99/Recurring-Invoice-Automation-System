from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """Page-number pagination with a client-selectable, capped page size.

    Response shape (identical for every list endpoint, so React needs one parser):
        {"count": 120, "page": 2, "page_size": 25, "total_pages": 5,
         "next": "...", "previous": "...", "results": [...]}
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100  # stop clients from requesting 1,000,000 rows in one call

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        base = super().get_paginated_response_schema(schema)
        base["properties"].update(
            {
                "page": {"type": "integer", "example": 1},
                "page_size": {"type": "integer", "example": 25},
                "total_pages": {"type": "integer", "example": 5},
            }
        )
        return base
