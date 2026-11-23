# Template lookup and generic fallback adapted from django-ajax-datatable
# (AjaxDatatableView.render_row_details), Copyright (c) 2017, Mario Orlandi,
# MIT License; see THIRD_PARTY_NOTICES.

from typing import Optional

from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.html import escape

from ninja_datatables.conf import get_setting


def detail_template_name(model, template: Optional[str] = None) -> str:
    pattern = template or get_setting("DETAIL_TEMPLATE")
    return pattern.format(app_label=model._meta.app_label, model_name=model._meta.model_name)


def render_row_details(model, obj, request, template: Optional[str] = None) -> str:
    """Renders the row-detail expansion HTML for a datatable row.

    Uses `template` (or the `DETAIL_TEMPLATE` setting), formatted with the
    model's `app_label`/`model_name` and rendered with `{"model", "object"}`
    in context. If that template doesn't exist, falls back to a generic
    `<table class="row-details">` with one escaped row per concrete field."""
    try:
        return render_to_string(
            detail_template_name(model, template), {"model": model, "object": obj}, request=request
        )
    except TemplateDoesNotExist:
        pass

    rows = []
    for f in [*model._meta.fields, *model._meta.many_to_many]:
        if f.many_to_many:
            value = ", ".join(str(x) for x in getattr(obj, f.name).all())
        else:
            try:
                value = getattr(obj, f.name)
            except AttributeError:
                continue
        label = getattr(f, "verbose_name", f.name)
        rows.append(f"<tr><td>{escape(label)}</td><td>{escape('' if value is None else value)}</td></tr>")
    return '<table class="row-details">' + "".join(rows) + "</table>"
