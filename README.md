# django-ninja-datatables

Server-side [DataTables](https://datatables.net/) listings served by
[django-ninja](https://django-ninja.dev/) endpoints, plus a small jQuery client
(`ninja-datatable.js`).

- One call registers a listing (`GET .../datatables/<slug>/`) and an expandable
  per-row detail (`GET .../datatables/<slug>/{id}/detail/`).
- Global search, per-column filters (text, select, date, booleans, custom
  filters), multi-column ordering restricted to a whitelist of fields, and pagination.
- Permissions: `<app>.view_<model>` by default; can be replaced or disabled.
- For endpoints with their own logic (annotations, complex querysets):
  `datatable_response()`.

## Installation

```bash
pip install "git+https://github.com/WillyLobo/django-ninja-datatables.git@main"
```

Pin a tag or commit instead of `@main` in a `requirements.txt`.

```python
INSTALLED_APPS = [
    # ...
    "ninja_datatables",   # so {% static %} can serve the JS client
]
```

Requires Python ≥ 3.10, Django ≥ 4.2 and django-ninja ≥ 1.1. On the frontend:
jQuery and DataTables 2.x.

## Backend

```python
from ninja import NinjaAPI, Router
from ninja.security import django_auth
from ninja_datatables import register_datatable, clip_value_html

router = Router()

def company_row(obj, user):
    actions = ""
    if user.has_perm("app.change_company"):
        actions = f'<a href="/companies/{obj.pk}/edit/">Edit</a>'
    return {
        "id": obj.pk,
        "name": clip_value_html(obj.name, 60),
        "tax_id": obj.tax_id,
        "active": "Yes" if obj.active else "No",
        "actions": actions,
    }

register_datatable(
    router, Company, "companies",
    row_builder=company_row,
    order_fields={"id": "id", "name": "name", "tax_id": "tax_id"},
    filter_fields={"name": "name__icontains", "tax_id": "tax_id__icontains", "active": "active"},
    search_lookups=["name__icontains", "tax_id__icontains"],
    boolean_filter_keys={"active"},
    default_order="name",
)

api = NinjaAPI(auth=django_auth)
api.add_router("", router)
```

`register_datatable` parameters:

| Parameter | Purpose |
|---|---|
| `row_builder(obj, user) -> dict` | Builds one row. Keys must match each client column's `data`. Returned HTML is inserted as-is, so escape values (`clip_value_html` already does). |
| `order_fields` | Column key → ORM field. Only these columns can be ordered by; an unknown key orders by `pk`. |
| `filter_fields` | Column key → ORM lookup for that column's filter. Keys not listed are ignored. |
| `search_lookups` | Lookups OR-ed together for the global search box. |
| `default_order` | Ordering when the client sends none (`"-date"`, `"name"`, …). |
| `queryset` | Base queryset, or `fn(request) -> queryset` to scope rows per user. Also applies to the detail endpoint. |
| `boolean_filter_keys` | Filters whose `"true"`/`"false"` strings are coerced to bool. |
| `custom_filters` | Key → `fn(qs, value) -> qs`, for filters that aren't a single lookup. |
| `distinct_filter_keys` | Filters that cross a many-to-many relation: they add `.distinct()`. |
| `permission` | View decorator. Defaults to `require_model_perm(model)`; `None` means only the router's `auth` applies. |
| `with_detail` / `detail_template` / `detail_suffix` | Detail endpoint, its template and the last segment of its URL (see below). |
| `max_length` | Maximum rows per page (also caps `length=-1`). |
| `url_prefix` | Defaults to `"/datatables/"`. |

### Hand-written endpoints

```python
from ninja import Query
from ninja.decorators import decorate_view
from ninja_datatables import DatatableParams, DatatableResponse, datatable_response, require_model_perm

@router.get("/datatables/projects/", response=DatatableResponse)
@decorate_view(require_model_perm(Project))
def datatable_projects(request, params: Query[DatatableParams]):
    qs = Project.objects.select_related("company").annotate(...)
    return datatable_response(
        request, qs, params,
        row_builder=project_row,
        order_fields=PROJECT_ORDER_FIELDS,
        filter_fields=PROJECT_FILTER_FIELDS,
        search_lookups=["name__icontains", "company__name__icontains"],
        distinct_filter_keys={"town"},
        default_order="-id",
    )
```

For finer control the building blocks are public too: `parse_filters`,
`apply_filters`, `apply_search`, `parse_order_by` and `paginate`.

### Row detail

The detail endpoint (`<prefix><slug>/{id}/detail/`) renders `ninja_datatables/<app_label>/<model_name>/row_details.html`
with `object` and `model` in the context. If that template doesn't exist, it falls
back to a generic, escaped field/value table. Both the template pattern and the
URL's last segment can be set globally, or per listing with `detail_template=` and
`detail_suffix=`:

```python
NINJA_DATATABLES = {
    "DETAIL_TEMPLATE": "myapp/{app_label}/{model_name}/details.html",
    "DETAIL_SUFFIX": "info",   # -> <prefix><slug>/{id}/info/  (default: "detail")
    "MAX_LENGTH": 1000,        # None (default) = no cap
}
```

`DETAIL_SUFFIX` is read when each listing is registered, so it must be set in
`settings.py` rather than changed at runtime. Keep the client's `detailUrl` in sync.

## Frontend

```html
{% load static %}
<script src="{% static 'ninja_datatables/i18n/es.js' %}"></script>   <!-- optional: Spanish UI -->
<script src="{% static 'ninja_datatables/ninja-datatable.js' %}"></script>

<table id="companies" class="table table-striped"></table>
<script>
  NinjaDatatableUtils.initialize_table($('#companies'), '/api/datatables/companies/', [
      { data: 'id', title: 'Id' },
      { data: 'name', title: 'Name' },
      { data: 'tax_id', title: 'Tax ID' },
      { data: 'active', title: 'Active', filterType: 'select',
        filterChoices: [['true', 'Yes'], ['false', 'No']] },
      { data: 'actions', title: 'Actions', orderable: false, searchable: false },
  ], {
      order: [[1, 'asc']],
      lengthMenu: [[50, 100, -1], [50, 100, 'All']],
      detailUrl: '/api/datatables/companies/{id}/detail/',
  });
</script>
```

Column options on top of DataTables' own: `filterable: false`,
`filterType: 'select' | 'date'`, `filterChoices`, and `filterChoicesUrl` (an endpoint
returning `{choices: [[value, label], ...]}`). The key sent to the backend is the
column's `name`, or its `data` when there is no `name`.

`initialize_table` options:
- **Table:** `order`, `lengthMenu`, `layout`.
- **Row detail:** `detailUrl`, `idField`.
- **Filters:** `columnFilters`, `filterDelay`, and `extraFilters` (a function returning
  extra filters, e.g. from controls outside the table).
- **Text:** `language` (a DataTables language object), `loadingText` and `errorText`
  (row-detail messages). They default to English. Loading `i18n/es.js`, before or
  after the client, switches the defaults to Spanish; a file for another language
  follows the same shape (`window.DATATABLES_ES`-style language object plus
  `window.NINJA_DATATABLES_I18N = {loadingText, errorText}`).
- **Styling:** `classes` (CSS classes for the filter inputs and selects, Bootstrap 5
  by default).
- **Overrides:** `dataTableOptions` takes raw DataTables options and overrides
  everything else.

It returns the DataTables instance, so `table.draw()` reloads the table.

## HTTP contract

Request (`GET`, query string):

| Parameter | Example |
|---|---|
| `draw` | `3` |
| `start`, `length` | `0`, `50` (`-1` = all rows) |
| `search` | `school` |
| `order_by` | `-date,name` |
| `filters` | `{"active": "true", "name": "ab"}` (JSON) |

Response: `{"draw": 3, "recordsTotal": 120, "recordsFiltered": 8, "data": [{...}, ...]}`.
Detail endpoint: `{"html": "..."}`.

## Development

```bash
uv venv && uv pip install -e ".[test]"
.venv/bin/pytest
```

## Credits

This package is based on
[django-ajax-datatable](https://github.com/morlandi/django-ajax-datatable) by
Mario Orlandi (MIT license). Its server-side listing model, the per-column filter
row, the expandable row details with per-model templates, and the cell truncation
helper were the starting point for this package, which reimplements them on top
of django-ninja endpoints with statically declared columns and a simpler request
contract. If you don't use django-ninja, django-ajax-datatable is probably what
you want.

Some portions are adapted directly from django-ajax-datatable. They are listed,
together with its copyright notice (Copyright (c) 2017, Mario Orlandi) and license
text, in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).

## License

MIT (see [LICENSE](LICENSE)). Portions adapted from django-ajax-datatable keep
their original MIT copyright notice; see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
