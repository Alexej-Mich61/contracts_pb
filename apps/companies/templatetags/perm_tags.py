# apps/companies/templatetags/perm_tags.py
from django import template
from apps.companies.permissions import ContractPermission

register = template.Library()


@register.simple_tag(takes_context=True)
def can_delete_contract(context, company):
    user = context["request"].user
    return ContractPermission(user, company).can_delete()


@register.simple_tag(takes_context=True)
def can_edit_systems(context, company):
    user = context["request"].user
    return ContractPermission(user, company).can_edit_systems()


@register.simple_tag(takes_context=True)
def can_edit_sign_stage(context, company):
    user = context["request"].user
    return ContractPermission(user, company).can_edit_sign_stage()