# apps/contract_core/services/ak_filter_service.py
from django.db.models import Q, QuerySet
from ..models import Ak


class AkFilterService:
    """Сервис для фильтрации абонентских комплектов (АК)."""

    def __init__(self, request_get: dict):
        self.params = request_get

    def filter(self, queryset: QuerySet = None) -> QuerySet:
        """Применяет все фильтры к queryset."""
        if queryset is None:
            qs = Ak.objects.all().select_related('district__region').order_by('-id')
        else:
            qs = queryset.select_related('district__region').order_by('-id')

        # Поиск по ID
        id_search = self.params.get('id', '').strip()
        if id_search and id_search.isdigit():
            qs = qs.filter(id=int(id_search))

        # Поиск по номеру АК
        number_search = self.params.get('number', '').strip()
        if number_search and number_search.isdigit():
            qs = qs.filter(number=int(number_search))

        # Поиск по названию
        name_search = self.params.get('name', '').strip()
        if name_search:
            qs = qs.filter(name__icontains=name_search)

        # Поиск по адресу
        address_search = self.params.get('address', '').strip()
        if address_search:
            qs = qs.filter(address__icontains=address_search)

        # Фильтр по региону
        region_id = self.params.get('region', '').strip()
        if region_id and region_id.isdigit():
            qs = qs.filter(district__region_id=int(region_id))

        # Фильтр по району
        district_id = self.params.get('district', '').strip()
        if district_id and district_id.isdigit():
            qs = qs.filter(district_id=int(district_id))

        return qs

    def has_active_filters(self) -> bool:
        """Проверяет, есть ли активные фильтры."""
        return bool(
            self.params.get('id') or
            self.params.get('number') or
            self.params.get('name') or
            self.params.get('address') or
            self.params.get('region') or
            self.params.get('district')
        )

    def get_context_data(self) -> dict:
        """Возвращает данные для контекста шаблона."""
        return {
            'search_id': self.params.get('id', ''),
            'search_number': self.params.get('number', ''),
            'search_name': self.params.get('name', ''),
            'search_address': self.params.get('address', ''),
            'selected_region': self.params.get('region', ''),
            'selected_district': self.params.get('district', ''),
        }