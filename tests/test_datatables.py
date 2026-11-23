import datetime
import json

import pytest
from django.contrib.auth.models import Permission, User

from ninja_datatables import clip_value_html, format_thousands, parse_filters, parse_order_by
from tests.testapp.models import Category, Item, Note, Tag

pytestmark = pytest.mark.django_db

URL = "/api/datatables/items/"


@pytest.fixture
def data():
    fruit = Category.objects.create(name="Fruta")
    veg = Category.objects.create(name="Verdura")
    red = Tag.objects.create(name="rojo")
    green = Tag.objects.create(name="verde")
    a = Item.objects.create(name="Manzana", code="M-1", active=True, category=fruit,
                            created=datetime.date(2026, 1, 10), owner="ana")
    b = Item.objects.create(name="Banana", code="B-2", active=False, category=fruit, owner="ana")
    c = Item.objects.create(name="Zanahoria", code="Z-3", active=True, category=veg, owner="ana")
    d = Item.objects.create(name="Tomate", code="T-4", active=True, category=veg, owner="otro")
    a.tags.add(red, green)
    d.tags.add(red)
    return {"a": a, "b": b, "c": c, "d": d}


@pytest.fixture
def user():
    return User.objects.create_user("ana", password="x")


@pytest.fixture
def client_perm(client, user):
    user.user_permissions.add(Permission.objects.get(codename="view_item"))
    client.force_login(user)
    return client


def get(client, url=URL, **params):
    if "filters" in params and not isinstance(params["filters"], str):
        params["filters"] = json.dumps(params["filters"])
    return client.get(url, params)


def names(resp):
    return [row["name"] for row in resp.json()["data"]]


# --- auth / permissions ---

def test_anonymous_is_rejected(client, data):
    assert get(client).status_code == 401


def test_authenticated_without_perm_is_forbidden(client, user, data):
    client.force_login(user)
    assert get(client).status_code == 403
    assert client.get(f"{URL}{data['a'].id}/detail/").status_code == 403


def test_permission_none_only_requires_auth(client, user, data):
    client.force_login(user)
    resp = get(client, "/api/datatables/mis-items/")
    assert resp.status_code == 200


# --- response envelope ---

def test_envelope_and_row_builder(client_perm, data):
    resp = get(client_perm, draw=7, order_by="id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["draw"] == 7
    assert body["recordsTotal"] == 4
    assert body["recordsFiltered"] == 4
    assert body["data"][0] == {
        "id": data["a"].id, "name": "Manzana", "active": True, "category": "Fruta", "user": "ana",
    }


def test_default_order_is_pk(client_perm, data):
    assert names(get(client_perm)) == ["Manzana", "Banana", "Zanahoria", "Tomate"]


# --- ordering ---

def test_order_desc_and_mapped_field(client_perm, data):
    assert names(get(client_perm, order_by="-name")) == ["Zanahoria", "Tomate", "Manzana", "Banana"]
    # "category" maps to category__name; ties broken by pk.
    assert names(get(client_perm, order_by="category")) == ["Manzana", "Banana", "Zanahoria", "Tomate"]


def test_multi_column_order(client_perm, data):
    assert names(get(client_perm, order_by="-category,name")) == ["Tomate", "Zanahoria", "Banana", "Manzana"]


def test_unknown_order_key_falls_back_to_pk(client_perm, data):
    assert names(get(client_perm, order_by="-password")) == ["Tomate", "Zanahoria", "Banana", "Manzana"]


# --- search & filters ---

def test_search_ors_lookups(client_perm, data):
    body = get(client_perm, search="z-3").json()
    assert [r["name"] for r in body["data"]] == ["Zanahoria"]
    assert body["recordsTotal"] == 4
    assert body["recordsFiltered"] == 1


def test_text_filter(client_perm, data):
    assert names(get(client_perm, filters={"name": "ana"})) == ["Manzana", "Banana", "Zanahoria"]


@pytest.mark.parametrize("value, expected", [("true", 3), ("false", 1), ("1", 3)])
def test_boolean_filter_coerced(client_perm, data, value, expected):
    assert get(client_perm, filters={"active": value}).json()["recordsFiltered"] == expected


def test_date_filter(client_perm, data):
    assert names(get(client_perm, filters={"created": "2026-01-10"})) == ["Manzana"]


def test_empty_and_unknown_filters_ignored(client_perm, data):
    body = get(client_perm, filters={"name": "", "owner": "otro", "active": None}).json()
    assert body["recordsFiltered"] == 4


def test_malformed_filters_ignored(client_perm, data):
    assert get(client_perm, filters="{not json").json()["recordsFiltered"] == 4
    assert get(client_perm, filters="[1, 2]").json()["recordsFiltered"] == 4


def test_m2m_filter_is_distinct(client_perm, data):
    body = get(client_perm, filters={"tag": "rojo"}).json()
    assert body["recordsFiltered"] == 2
    assert sorted(r["name"] for r in body["data"]) == ["Manzana", "Tomate"]


def test_custom_filter(client_perm, data):
    assert names(get(client_perm, filters={"name_or_code": "t-4"})) == ["Tomate"]


# --- pagination ---

def test_start_and_length(client_perm, data):
    body = get(client_perm, start=1, length=2).json()
    assert [r["name"] for r in body["data"]] == ["Banana", "Zanahoria"]
    assert body["recordsFiltered"] == 4


def test_length_minus_one_returns_all(client_perm, data):
    assert len(get(client_perm, length=-1).json()["data"]) == 4


def test_negative_start_is_rejected(client_perm, data):
    assert get(client_perm, start=-1).status_code == 422


def test_max_length_caps_page(client, user, data):
    client.force_login(user)
    body = get(client, "/api/datatables/mis-items/", length=-1).json()
    assert len(body["data"]) == 2


def test_max_length_setting(client_perm, data, settings):
    settings.NINJA_DATATABLES = {"MAX_LENGTH": 1}
    assert len(get(client_perm, length=100).json()["data"]) == 1


# --- queryset scoping ---

def test_callable_queryset_scopes_list_and_detail(client, user, data):
    client.force_login(user)
    body = get(client, "/api/datatables/mis-items/", length=-1, order_by="id").json()
    assert body["recordsTotal"] == 3
    assert client.get(f"/api/datatables/mis-items/{data['d'].id}/detail/").status_code == 404
    assert client.get(f"/api/datatables/mis-items/{data['a'].id}/detail/").status_code == 200


# --- detail ---

def test_detail_uses_model_template(client_perm, data):
    resp = client_perm.get(f"{URL}{data['a'].id}/detail/")
    assert resp.status_code == 200
    assert resp.json()["html"].strip() == '<div class="custom-detail">Manzana (M-1)</div>'


def test_detail_generic_fallback_escapes(client_perm, data, settings):
    settings.NINJA_DATATABLES = {"DETAIL_TEMPLATE": "missing/{app_label}/{model_name}.html"}
    data["a"].name = "<b>Manzana</b>"
    data["a"].save()
    html = client_perm.get(f"{URL}{data['a'].id}/detail/").json()["html"]
    assert html.startswith('<table class="row-details">')
    assert "<td>nombre</td><td>&lt;b&gt;Manzana&lt;/b&gt;</td>" in html
    assert "<td>tags</td><td>rojo, verde</td>" in html
    assert "<td>created</td><td>2026-01-10</td>" in html


def test_detail_404(client_perm, data):
    assert client_perm.get(f"{URL}999999/detail/").status_code == 404


def test_with_detail_false(client, user):
    user.user_permissions.add(Permission.objects.get(codename="view_note"))
    client.force_login(user)
    Note.objects.create(text="hola")
    assert get(client, "/api/datatables/notes/").json()["recordsTotal"] == 1
    assert client.get("/api/datatables/notes/1/detail/").status_code == 404


def test_custom_detail_suffix(client, user):
    user.user_permissions.add(Permission.objects.get(codename="view_note"))
    client.force_login(user)
    note = Note.objects.create(text="hola")
    assert client.get(f"/api/datatables/notas/{note.id}/detalle/").status_code == 200
    assert client.get(f"/api/datatables/notas/{note.id}/detail/").status_code == 404


def test_detail_suffix_setting(settings):
    from ninja import Router
    from ninja_datatables import register_datatable

    settings.NINJA_DATATABLES = {"DETAIL_SUFFIX": "info"}
    router = Router()
    register_datatable(router, Note, "x", row_builder=lambda o, u: {}, order_fields={})
    assert {"/datatables/x/", "/datatables/x/{id}/info/"} == set(router.path_operations)


def test_empty_detail_suffix_rejected(settings):
    from ninja import Router
    from ninja_datatables import register_datatable

    settings.NINJA_DATATABLES = {"DETAIL_SUFFIX": "/"}
    with pytest.raises(ValueError):
        register_datatable(Router(), Note, "x", row_builder=lambda o, u: {}, order_fields={})


# --- hand-written endpoint using datatable_response ---

def test_manual_endpoint(client_perm, data):
    body = get(client_perm, "/api/datatables/manual-items/").json()
    assert body["recordsTotal"] == 3
    assert [r["name"] for r in body["data"]] == ["Zanahoria", "Tomate", "Manzana"]


def test_openapi_schema_lists_operations(client, data):
    from django.contrib.auth.models import User as U
    client.force_login(U.objects.create_superuser("admin", password="x"))
    schema = client.get("/api/openapi.json").json()
    op_ids = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert {"datatable_items_list", "datatable_items_detail", "datatable_mis_items_list",
            "datatable_notes_list"} <= op_ids


# --- pure helpers ---

def test_parse_order_by():
    fields = {"a": "field_a", "b": "rel__b"}
    assert parse_order_by("a,-b", fields) == ["field_a", "-rel__b"]
    assert parse_order_by(" , ", fields) == ["id"]
    assert parse_order_by("-zzz", fields, "pk") == ["-pk"]


def test_parse_filters():
    assert parse_filters('{"a": 1}') == {"a": 1}
    assert parse_filters("") == {}
    assert parse_filters(None) == {}
    assert parse_filters('"x"') == {}


def test_format_thousands():
    assert format_thousands(1234567.891) == "1.234.567,89"
    assert format_thousands(0) == "0,00"
    assert format_thousands(-1500) == "-1.500,00"
    assert format_thousands(1234.5, decimals=0, thousands_sep=",", decimal_sep=".") == "1,234"


def test_clip_value_html():
    assert clip_value_html("abc", 5) == '<span title="abc">abc</span>'
    assert clip_value_html("<abcdef>", 3) == '<span title="&lt;abcdef&gt;">&lt;ab&hellip;</span>'
