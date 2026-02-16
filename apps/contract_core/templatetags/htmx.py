# contract_core/templatetags/htmx.py
# from django import template
# from django.utils.safestring import mark_safe
#
# register = template.Library()
#
# @register.simple_tag
# def htmx_script():
#     return mark_safe("""
#         <script src="https://unpkg.com/htmx.org@2.0.3" integrity="sha384-..." crossorigin="anonymous"></script>
#         <!-- опционально loading-states -->
#         <script src="https://unpkg.com/htmx.org@2.0.3/dist/ext/loading-states.js"></script>
#     """)