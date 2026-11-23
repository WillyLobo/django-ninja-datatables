"""Package settings, read from the `NINJA_DATATABLES` dict in Django settings.

    NINJA_DATATABLES = {
        # Template looked up for a row's detail expansion; formatted with the
        # model's `app_label` and `model_name`. Falls back to a generic
        # field/value table when it doesn't exist.
        "DETAIL_TEMPLATE": "ninja_datatables/{app_label}/{model_name}/row_details.html",
        # Last path segment of the detail endpoint: <prefix><slug>/{id}/<suffix>/.
        # Read when each listing is registered (i.e. at import time).
        "DETAIL_SUFFIX": "detail",
        # Upper bound for `length` (rows per page); None = no cap, and
        # `length=-1` ("all") is honoured.
        "MAX_LENGTH": None,
    }
"""

from django.conf import settings

DEFAULTS = {
    "DETAIL_TEMPLATE": "ninja_datatables/{app_label}/{model_name}/row_details.html",
    "DETAIL_SUFFIX": "detail",
    "MAX_LENGTH": None,
}


def get_setting(name):
    return getattr(settings, "NINJA_DATATABLES", {}).get(name, DEFAULTS[name])
