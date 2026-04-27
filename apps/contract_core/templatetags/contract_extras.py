# apps/contract_core/templatetags/contract_extras.py
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Преобразует текущий GET-запрос, заменяя или добавляя параметры.

    Использование в шаблоне:
        {% query_transform page=2 %}
        {% query_transform page=1 %}
        {% query_transform page=None %}   {# удалить параметр #}
        {% query_transform page=5 filter=active %}

    Автоматически берёт request из context.
    """
    # Получаем копию текущих GET-параметров
    query_dict = context['request'].GET.copy()

    for key, value in kwargs.items():
        if value is None or value == '' or value == 'None':
            # Удаляем параметр
            query_dict.pop(key, None)
        else:
            # Добавляем или заменяем параметр
            query_dict[key] = str(value)

    return query_dict.urlencode()


@register.simple_tag(takes_context=True)
def active_page(context, page_number):
    """Возвращает 'active', если это текущая страница (для цифровой пагинации)"""
    try:
        current = int(context.get('page_obj', {}).number)
        target = int(page_number)
        return 'active' if current == target else ''
    except (TypeError, ValueError, AttributeError, KeyError):
        return ''


@register.filter
def is_htmx(request):
    """Проверка, является ли запрос HTMX"""
    if not request:
        return False
    return bool(getattr(request, 'headers', {}).get('HX-Request'))