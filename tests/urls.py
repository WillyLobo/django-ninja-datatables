from django.urls import path
from ninja import NinjaAPI, Query, Router
from ninja.decorators import decorate_view
from ninja.security import django_auth

from ninja_datatables import (
    DatatableParams,
    DatatableResponse,
    datatable_response,
    register_datatable,
    require_model_perm,
)
from tests.testapp.models import Item, Note

router = Router()


def item_row(obj, user):
    return {
        "id": obj.id,
        "name": obj.name,
        "active": obj.active,
        "category": str(obj.category or ""),
        "user": user.username,
    }


register_datatable(
    router, Item, "items",
    row_builder=item_row,
    order_fields={"id": "id", "name": "name", "category": "category__name"},
    filter_fields={
        "name": "name__icontains",
        "active": "active",
        "created": "created",
        "tag": "tags__name",
    },
    search_lookups=["name__icontains", "code__icontains"],
    boolean_filter_keys={"active"},
    distinct_filter_keys={"tag"},
    custom_filters={"name_or_code": lambda qs, v: qs.filter(name__icontains=v) | qs.filter(code__icontains=v)},
)

# Per-request scoping, no detail endpoint, model perm replaced by auth-only.
register_datatable(
    router, Item, "mis-items",
    row_builder=item_row,
    order_fields={"id": "id"},
    queryset=lambda request: Item.objects.filter(owner=request.user.username),
    with_detail=True,
    permission=None,
    max_length=2,
)

register_datatable(
    router, Note, "notas",
    row_builder=lambda o, u: {"id": o.id, "text": o.text},
    order_fields={"id": "id"},
    detail_suffix="/detalle/",
)

register_datatable(
    router, Note, "notes",
    row_builder=lambda o, u: {"id": o.id, "text": o.text},
    order_fields={"id": "id"},
    with_detail=False,
)


@router.get("/datatables/manual-items/", response=DatatableResponse)
@decorate_view(require_model_perm(Item))
def manual_items(request, params: Query[DatatableParams]):
    return datatable_response(
        request, Item.objects.filter(active=True), params,
        row_builder=item_row,
        order_fields={"name": "name"},
        default_order="-name",
    )


api = NinjaAPI(auth=django_auth, urls_namespace="test-api")
api.add_router("", router)

urlpatterns = [path("api/", api.urls)]
