from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rs(value):
    """Format a number as 'Rs 3,200' (no decimals)."""
    try:
        value = Decimal(value or 0)
    except (InvalidOperation, TypeError):
        return value
    return f'Rs {value:,.0f}'


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Return a querystring based on the current GET params with overrides.

    Pass ``key='__clear__'`` (or an empty value) to drop that param. ``page`` is
    always reset so changing a filter sends you back to page 1.
    """
    request = context['request']
    params = request.GET.copy()
    params.pop('page', None)
    for key, value in kwargs.items():
        if value in (None, '', '__clear__'):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f'?{encoded}' if encoded else ''


@register.filter
def meters(value):
    """Trim trailing zeros from a meter figure: 3.50 -> 3.5, 4.00 -> 4."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError):
        return value
    return f'{value.normalize():f}'
