# apps/contract_core/services/company_filter_service.py
from django.db.models import Q, QuerySet
from ..models import Company


class CompanyFilterService:
    """Сервис для фильтрации компаний."""

    def __init__(self, request_get: dict):
        self.params = request_get

    def filter(self, queryset: QuerySet = None) -> QuerySet:
        """Применяет все фильтры к queryset."""
        if queryset is None:
            qs = Company.objects.all().order_by('-id')
        else:
            qs = queryset.order_by('-id')

        # Поиск по ID
        id_search = self.params.get('id', '').strip()
        if id_search and id_search.isdigit():
            qs = qs.filter(id=int(id_search))

        # Поиск по названию/ИНН
        q = self.params.get('q', '').strip()
        if q:
            qs = qs.filter(Q(inn__icontains=q) | Q(name__icontains=q))

        # Фильтр по ролям
        roles = self.params.getlist('role')
        if roles:
            role_filters = Q()
            if 'customer' in roles:
                role_filters |= Q(is_customer=True)
            if 'licensee' in roles:
                role_filters |= Q(is_licensee=True)
            if 'laboratory' in roles:
                role_filters |= Q(is_laboratory=True)
            if 'subcontractor' in roles:
                role_filters |= Q(is_subcontractor=True)
            qs = qs.filter(role_filters)

        # Фильтр по согласию на уведомление
        notification = self.params.get('notification', '').strip()
        if notification == 'yes':
            qs = qs.filter(notification_agreed=True)
        elif notification == 'no':
            qs = qs.filter(notification_agreed=False)

        return qs.distinct()

    def has_active_filters(self) -> bool:
        """Проверяет, есть ли активные фильтры."""
        return bool(
            self.params.get('q') or
            self.params.get('id') or
            self.params.getlist('role') or
            self.params.get('notification')
        )

    def get_context_data(self) -> dict:
        """Возвращает данные для контекста шаблона."""
        return {
            'selected_roles': self.params.getlist('role'),
            'search_id': self.params.get('id', ''),
            'search_q': self.params.get('q', ''),
            'selected_notification': self.params.get('notification', ''),
        }