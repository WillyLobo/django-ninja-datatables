"""Server-side DataTables contract on top of django-ninja.

The request is a flat querystring (see `DatatableParams`) instead of DataTables'
bracketed `columns[0][search][value]` format, and the response is the standard
`{draw, recordsTotal, recordsFiltered, data}` envelope DataTables expects.
`static/ninja_datatables/ninja-datatable.js` is the matching client.
"""

import json
from typing import Any, Callable, Iterable, Mapping, Optional

from django.db.models import Q, QuerySet
from ninja import Field, Schema

from ninja_datatables.conf import get_setting

TRUE_STRINGS = frozenset({"true", "True", "1", "on", "yes"})


class DatatableParams(Schema):
    """Querystring sent by `NinjaDatatableUtils.initialize_table()`.

    Use it in a hand-written endpoint as `params: Query[DatatableParams]` and pass
    it to `datatable_response()`. `order_by` is a comma-separated list of column
    keys, each optionally prefixed with '-' for descending order; `filters` is a
    JSON object mapping column keys to the value typed/selected in that column's
    filter. `length=-1` means "all rows"."""

    draw: int = 1
    start: int = Field(0, ge=0)
    length: int = Field(50, ge=-1)
    search: str = ""
    order_by: str = ""
    filters: str = "{}"


class DatatableResponse(Schema):
    draw: int
    recordsTotal: int
    recordsFiltered: int
    data: list[Any]


class DetailResponse(Schema):
    html: str


def parse_order_by(order_by: str, fields_map: Mapping[str, str], default_field: str = "id") -> list[str]:
    """Turns a comma-separated, optionally '-'-prefixed list of datatable column
    keys into ORM `order_by()` clauses, mapping each key through `fields_map`.

    Unknown keys fall back to `default_field`, so the client can never order by
    an arbitrary (possibly sensitive or unindexed) field."""
    clauses = []
    for part in filter(None, (p.strip() for p in (order_by or "").split(","))):
        desc = part.startswith("-")
        key = part[1:] if desc else part
        field = fields_map.get(key, default_field)
        clauses.append(f"-{field}" if desc else field)
    return clauses or [default_field]


def parse_filters(filters: Optional[str]) -> dict:
    """Decodes the `filters` JSON object; anything malformed yields no filters."""
    try:
        value = json.loads(filters or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def apply_filters(
    qs: QuerySet,
    active_filters: Mapping[str, Any],
    filter_fields: Mapping[str, str],
    *,
    boolean_filter_keys: Iterable[str] = (),
    custom_filters: Optional[Mapping[str, Callable[[QuerySet, Any], QuerySet]]] = None,
    distinct_filter_keys: Iterable[str] = (),
) -> QuerySet:
    """Applies the per-column filters sent by the client.

    - `filter_fields` maps a column key to a single ORM lookup
      (e.g. `{"name": "name__icontains"}`); keys not listed are ignored.
    - `boolean_filter_keys` coerces the "true"/"false" strings of a <select>
      filter before `.filter()`.
    - `custom_filters` maps a key to `fn(qs, value) -> qs`, for filters a single
      lookup can't express (e.g. an OR across several fields).
    - `distinct_filter_keys` adds `.distinct()` when any of those filters is
      active (e.g. lookups that cross a many-to-many and would duplicate rows).
    """
    boolean_filter_keys = frozenset(boolean_filter_keys)
    distinct_filter_keys = frozenset(distinct_filter_keys)
    needs_distinct = False
    for key, value in active_filters.items():
        if value in (None, ""):
            continue
        if custom_filters and key in custom_filters:
            qs = custom_filters[key](qs, value)
        else:
            lookup = filter_fields.get(key)
            if not lookup:
                continue
            if key in boolean_filter_keys:
                value = str(value) in TRUE_STRINGS
            qs = qs.filter(**{lookup: value})
        if key in distinct_filter_keys:
            needs_distinct = True
    return qs.distinct() if needs_distinct else qs


def apply_search(qs: QuerySet, search: str, search_lookups: Iterable[str]) -> QuerySet:
    """ORs `search` across every lookup in `search_lookups` (e.g. `name__icontains`)."""
    search_lookups = list(search_lookups)
    if not search or not search_lookups:
        return qs
    search_q = Q()
    for lookup in search_lookups:
        search_q |= Q(**{lookup: search})
    return qs.filter(search_q).distinct()


def paginate(qs: QuerySet, start: int, length: int, max_length: Optional[int] = None):
    """Slices one page. `length=-1` means all rows, unless `max_length` caps it."""
    if max_length is not None and (length == -1 or length > max_length):
        length = max_length
    return qs[start:] if length == -1 else qs[start:start + length]


def datatable_response(
    request,
    qs: QuerySet,
    params: DatatableParams,
    *,
    row_builder: Callable[[Any, Any], dict],
    order_fields: Mapping[str, str],
    filter_fields: Mapping[str, str] = None,
    search_lookups: Iterable[str] = (),
    default_order: str = "pk",
    boolean_filter_keys: Iterable[str] = (),
    custom_filters: Optional[Mapping[str, Callable[[QuerySet, Any], QuerySet]]] = None,
    distinct_filter_keys: Iterable[str] = (),
    tiebreaker: Optional[str] = "pk",
    max_length: Optional[int] = None,
) -> dict:
    """Filters, searches, orders and paginates `qs` according to `params` and
    returns the DataTables response envelope.

    `row_builder(obj, request.user) -> dict` turns each object into the row the
    client renders; its keys must match the `data` of each client column.
    `tiebreaker` is appended to the ordering so pagination is deterministic when
    the chosen column has repeated values (pass None to disable).
    `max_length` defaults to the `NINJA_DATATABLES["MAX_LENGTH"]` setting."""
    records_total = qs.count()

    qs = apply_filters(
        qs,
        parse_filters(params.filters),
        filter_fields or {},
        boolean_filter_keys=boolean_filter_keys,
        custom_filters=custom_filters,
        distinct_filter_keys=distinct_filter_keys,
    )
    qs = apply_search(qs, params.search, search_lookups)
    records_filtered = qs.count()

    ordering = parse_order_by(params.order_by or default_order, order_fields, "pk")
    if tiebreaker:
        ordering.append(tiebreaker)
    qs = qs.order_by(*ordering)

    if max_length is None:
        max_length = get_setting("MAX_LENGTH")
    page = paginate(qs, params.start, params.length, max_length)

    return {
        "draw": params.draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": [row_builder(obj, request.user) for obj in page],
    }
