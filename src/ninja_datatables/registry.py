from typing import Any, Callable, Iterable, Mapping, Optional, Union

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from ninja import Query
from ninja.decorators import decorate_view

from ninja_datatables.conf import get_setting
from ninja_datatables.core import DatatableParams, DatatableResponse, DetailResponse, datatable_response
from ninja_datatables.details import render_row_details
from ninja_datatables.permissions import require_model_perm

_DEFAULT = object()


def _resolve_permission(permission, model):
    """`_DEFAULT` -> model view permission; None/False -> no extra check
    (the router's `auth` still applies); anything else is used as a view decorator."""
    if permission is _DEFAULT:
        return require_model_perm(model)
    if not permission:
        return lambda func: func
    return permission


def register_datatable(
    router,
    model,
    url_slug: str,
    *,
    row_builder: Callable[[Any, Any], dict],
    order_fields: Mapping[str, str],
    filter_fields: Optional[Mapping[str, str]] = None,
    search_lookups: Iterable[str] = (),
    default_order: str = "pk",
    queryset: Union[QuerySet, Callable[[Any], QuerySet], None] = None,
    with_detail: bool = True,
    detail_template: Optional[str] = None,
    detail_suffix: Optional[str] = None,
    boolean_filter_keys: Iterable[str] = (),
    custom_filters: Optional[Mapping[str, Callable[[QuerySet, Any], QuerySet]]] = None,
    distinct_filter_keys: Iterable[str] = (),
    permission=_DEFAULT,
    max_length: Optional[int] = None,
    url_prefix: str = "/datatables/",
):
    """Registers `GET <url_prefix><url_slug>/` (+ `.../{id}/<detail_suffix>/` unless
    `with_detail=False`) on `router`, serving a server-side DataTables listing
    of `model`. Returns `(list_view, detail_view_or_None)`.

    - `row_builder(obj, user) -> dict`: one row; keys match the client columns' `data`.
    - `order_fields`: column key -> ORM field the client may order by.
    - `filter_fields`: column key -> ORM lookup for the per-column filters.
    - `search_lookups`: lookups OR-ed together for the global search box.
    - `queryset`: base queryset, or `fn(request) -> queryset` to scope rows per
      request (e.g. per user). Defaults to `model.objects.all()`.
    - `permission`: view decorator gating both endpoints. Defaults to the model's
      `view` permission; pass None to rely only on the router's `auth`.
    - `detail_template`: template pattern for the detail expansion (formatted
      with `app_label`/`model_name`); defaults to the `DETAIL_TEMPLATE` setting.
    - `detail_suffix`: last path segment of the detail endpoint; defaults to the
      `DETAIL_SUFFIX` setting (`"detail"`).
    - `boolean_filter_keys`, `custom_filters`, `distinct_filter_keys`: see
      `ninja_datatables.core.apply_filters`.
    """
    gate = _resolve_permission(permission, model)
    op_slug = url_slug.strip("/").replace("/", "_").replace("-", "_")

    def get_queryset(request):
        if callable(queryset):
            return queryset(request)
        return (model.objects.all() if queryset is None else queryset).all()

    @router.get(
        f"{url_prefix}{url_slug}/",
        response=DatatableResponse,
        operation_id=f"datatable_{op_slug}_list",
        summary=f"Datatable {model._meta.verbose_name_plural}",
    )
    @decorate_view(gate)
    def _list(request, params: Query[DatatableParams]):
        return datatable_response(
            request,
            get_queryset(request),
            params,
            row_builder=row_builder,
            order_fields=order_fields,
            filter_fields=filter_fields,
            search_lookups=search_lookups,
            default_order=default_order,
            boolean_filter_keys=boolean_filter_keys,
            custom_filters=custom_filters,
            distinct_filter_keys=distinct_filter_keys,
            max_length=max_length,
        )

    if not with_detail:
        return _list, None

    suffix = (detail_suffix or get_setting("DETAIL_SUFFIX")).strip("/")
    if not suffix:
        raise ValueError("detail_suffix / NINJA_DATATABLES['DETAIL_SUFFIX'] must not be empty")

    @router.get(
        f"{url_prefix}{url_slug}/{{id}}/{suffix}/",
        response=DetailResponse,
        operation_id=f"datatable_{op_slug}_detail",
        summary=f"Datatable {model._meta.verbose_name} detail",
    )
    @decorate_view(gate)
    def _detail(request, id: int):
        obj = get_object_or_404(get_queryset(request), pk=id)
        return {"html": render_row_details(model, obj, request, detail_template)}

    return _list, _detail


# Name used in the project this package was extracted from.
register_simple_datatable = register_datatable
