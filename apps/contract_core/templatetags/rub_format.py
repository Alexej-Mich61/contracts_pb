# apps/contract_core/templatetags/rub_format.py
from django import template
from django.utils.numberformat import format as format_number

register = template.Library()


@register.filter(name='rub')
def rub_format(value, decimal_places=2):
    """
    Форматирует число в рублевый формат:
    10000.00 -> 10 000,00
    """
    if value is None:
        value = 0

    return format_number(
        value,
        decimal_sep=',',
        decimal_pos=int(decimal_places),  # <-- исправлено: decimal_pos вместо decimal_places
        grouping=3,
        thousand_sep=' ',
        force_grouping=True,
    )