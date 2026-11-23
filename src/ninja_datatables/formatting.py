"""Helpers for building row cells in a `row_builder`."""

from django.utils.html import escape


def clip_value_html(text, max_length: int) -> str:
    """Wraps the value in a `<span title="full text">` and clips the visible text
    to `max_length` characters with an ellipsis. Both parts are HTML-escaped.

    Markup adapted from django-ajax-datatable's `clip_value`, Copyright (c) 2017,
    Mario Orlandi, MIT License; see THIRD_PARTY_NOTICES."""
    text = str(text)
    short = text if len(text) <= max_length else text[:max_length]
    html = f'<span title="{escape(text)}">{escape(short)}'
    if len(text) > max_length:
        html += "&hellip;"
    return html + "</span>"


def format_thousands(value, decimals: int = 2, thousands_sep: str = ".", decimal_sep: str = ",") -> str:
    """Formats a number with explicit separators (by default `1.234.567,89`)
    without touching the process-wide locale."""
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.translate(str.maketrans({",": "\0", ".": decimal_sep})).replace("\0", thousands_sep)
