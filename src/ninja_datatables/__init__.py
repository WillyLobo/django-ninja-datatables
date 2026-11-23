"""Server-side DataTables listings served by django-ninja endpoints.

Based on django-ajax-datatable (https://github.com/morlandi/django-ajax-datatable,
Copyright (c) 2017, Mario Orlandi, MIT License), reimplemented on top of
django-ninja. Portions adapted from it are listed in THIRD_PARTY_NOTICES.
"""

from ninja_datatables.core import (
    DatatableParams,
    DatatableResponse,
    DetailResponse,
    apply_filters,
    apply_search,
    datatable_response,
    paginate,
    parse_filters,
    parse_order_by,
)
from ninja_datatables.details import render_row_details
from ninja_datatables.formatting import clip_value_html, format_thousands
from ninja_datatables.pagination import PerPagePagination
from ninja_datatables.permissions import require_model_perm
from ninja_datatables.registry import register_datatable, register_simple_datatable

__version__ = "0.1.0"

__all__ = [
    "DatatableParams",
    "DatatableResponse",
    "DetailResponse",
    "PerPagePagination",
    "apply_filters",
    "apply_search",
    "clip_value_html",
    "datatable_response",
    "format_thousands",
    "paginate",
    "parse_filters",
    "parse_order_by",
    "register_datatable",
    "register_simple_datatable",
    "render_row_details",
    "require_model_perm",
]
