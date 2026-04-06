# contract_core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_field_label(form_fields, field_name):
    """Получить label поля по его имени"""
    if hasattr(form_fields, 'get'):
        field = form_fields.get(field_name)
        if field:
            return field.label
    return field_name