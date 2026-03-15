# apps/contract_core/services/subcontractors_to_filter_service.py
"""
Сервис для формирования отчета по субподрядчикам ТО.

Принцип единой ответственности: сервис отвечает только за:
- Фильтрацию объектов защиты по заданным критериям
- Агрегацию данных для сводной информации
- Формирование контекста для шаблона

Не отвечает за: HTTP-логику, рендеринг, права доступа (кроме базовой фильтрации по employee).
"""

from decimal import Decimal
from typing import Optional

from django.db.models import Q, QuerySet, Sum, Count
from django.core.paginator import Paginator, Page

from apps.contract_core.models import ProtectionObject, Contract, Company, Work, Ak
from apps.identity.models import Employee


class SubcontractorFilterDTO:
    """DTO для передачи параметров фильтрации."""

    def __init__(
            self,
            subcontractor_id: Optional[str] = None,
            subcontractor_search: Optional[str] = None,
            executor_ids: Optional[list] = None,
            work_ids: Optional[list] = None,
            page: int = 1,
    ):
        self.subcontractor_id = subcontractor_id
        self.subcontractor_search = subcontractor_search
        self.executor_ids = executor_ids or []
        self.work_ids = work_ids or []
        self.page = page


class SubcontractorReportResult:
    """DTO для результата отчета."""

    def __init__(
            self,
            protection_objects: Page,
            total_objects: int,
            total_aks: int,
            total_subcontract_sum: Decimal,
            total_monthly_subcontract_sum: Decimal,
    ):
        self.protection_objects = protection_objects
        self.total_objects = total_objects
        self.total_aks = total_aks
        self.total_subcontract_sum = total_subcontract_sum
        self.total_monthly_subcontract_sum = total_monthly_subcontract_sum


class SubcontractorToFilterService:
    """
    Сервис фильтрации объектов защиты по субподрядчикам.

    Отбирает объекты защиты из активных долгосрочных договоров ТО,
    фильтрует по субподрядчику, исполнителю и виду работ.
    """

    # Статусы активных договоров ТО
    ACTIVE_STATUSES = [
        Contract.STATUS_ACTIVE,
        Contract.STATUS_ACTIVE_EXPIRES,
    ]

    # Тип договора - долгосрочное ТО лицензиата
    CONTRACT_TYPE = Contract.Type.LONGTERM_TO_LICENSEE

    def __init__(self, user):
        """
        Инициализация сервиса.

        Args:
            user: Текущий пользователь для определения доступных компаний-исполнителей
        """
        self.user = user
        self._available_executor_ids: Optional[set] = None

    def _get_available_executor_ids(self) -> set:
        """
        Получает ID компаний-исполнителей, доступных пользователю.

        Суперпользователь видит все is_licensee.
        Обычный пользователь видит только компании, где он - сотрудник.

        Returns:
            Множество ID доступных компаний-исполнителей
        """
        if self._available_executor_ids is not None:
            return self._available_executor_ids

        if self.user.is_superuser:
            # Суперпользователь видит всех лицензиатов
            self._available_executor_ids = set(
                Company.objects.filter(is_licensee=True).values_list('id', flat=True)
            )
        else:
            # Обычный пользователь - только свои компании
            self._available_executor_ids = set(
                Employee.objects.filter(
                    user=self.user,
                    is_active=True,
                    company__is_licensee=True
                ).values_list('company_id', flat=True)
            )

        return self._available_executor_ids

    def _get_base_queryset(self) -> QuerySet:
        """
        Базовый queryset объектов защиты из активных договоров ТО.

        Returns:
            QuerySet с prefetch связанных данных
        """
        return ProtectionObject.objects.filter(
            contract__type=self.CONTRACT_TYPE,
            contract__status__in=self.ACTIVE_STATUSES,
            contract__is_trash=False,
            contract__is_archived=False,
        ).select_related(
            'contract',
            'contract__executor',
            'contract__work',
            'district',
            'district__region',
            'subcontractor',
        ).prefetch_related(
            'aks',
        ).order_by(
            'district__name',
            'address',
        )

    def _apply_executor_filter(
            self,
            qs: QuerySet,
            executor_ids: list
    ) -> QuerySet:
        """
        Применяет фильтр по компаниям-исполнителям.

        Пользователь может видеть только свои компании (или все, если суперюзер).
        """
        available_ids = self._get_available_executor_ids()

        if not available_ids:
            # У пользователя нет доступных компаний - пустой результат
            return qs.none()

        # Если указаны конкретные исполнители - фильтруем по ним
        # с пересечением с доступными
        if executor_ids:
            requested_ids = {int(eid) for eid in executor_ids if str(eid).isdigit()}
            allowed_ids = requested_ids & available_ids
            if not allowed_ids:
                return qs.none()
            return qs.filter(contract__executor_id__in=allowed_ids)

        # Иначе - все доступные компании
        return qs.filter(contract__executor_id__in=available_ids)

    def _apply_subcontractor_filter(
            self,
            qs: QuerySet,
            dto: SubcontractorFilterDTO
    ) -> QuerySet:
        """Применяет фильтр по субподрядчику (ID или поиск по названию/ИНН)."""
        # Приоритет у ID
        if dto.subcontractor_id and str(dto.subcontractor_id).isdigit():
            return qs.filter(subcontractor_id=int(dto.subcontractor_id))

        # Поиск по названию или ИНН
        if dto.subcontractor_search:
            search = dto.subcontractor_search.strip()
            if len(search) >= 2:  # Минимум 2 символа для поиска
                qs = qs.filter(
                    Q(subcontractor__name__icontains=search) |
                    Q(subcontractor__inn__icontains=search)
                )

        return qs

    def _apply_work_filter(self, qs: QuerySet, work_ids: list) -> QuerySet:
        """Применяет фильтр по видам работ."""
        if not work_ids:
            return qs

        valid_ids = [int(wid) for wid in work_ids if str(wid).isdigit()]
        if valid_ids:
            return qs.filter(contract__work_id__in=valid_ids)

        return qs

    def filter(self, dto: SubcontractorFilterDTO) -> QuerySet:
        """
        Применяет все фильтры к queryset.

        Args:
            dto: DTO с параметрами фильтрации

        Returns:
            Отфильтрованный QuerySet объектов защиты
        """
        qs = self._get_base_queryset()

        # Фильтр по исполнителям (обязательный - ограничение доступа)
        qs = self._apply_executor_filter(qs, dto.executor_ids)

        # Фильтр по субподрядчику
        qs = self._apply_subcontractor_filter(qs, dto)

        # Фильтр по видам работ
        qs = self._apply_work_filter(qs, dto.work_ids)

        return qs

    def _count_total_aks(self, filtered_qs: QuerySet) -> int:
        """
        Подсчитывает общее количество АК для отфильтрованных объектов защиты.

        Использует отдельный запрос через промежуточную таблицу Many-to-Many.
        """
        # Получаем ID объектов защиты
        protection_object_ids = filtered_qs.values_list('id', flat=True)

        # Считаем АК через промежуточную таблицу
        count = Ak.objects.filter(
            protection_objects__id__in=protection_object_ids
        ).distinct().count()

        return count

    def get_report_result(
            self,
            dto: SubcontractorFilterDTO,
            per_page: int = 30
    ) -> SubcontractorReportResult:
        """
        Формирует полный результат отчета с пагинацией и агрегацией.

        Args:
            dto: Параметры фильтрации
            per_page: Количество объектов на страницу

        Returns:
            SubcontractorReportResult с данными для отображения
        """
        # Получаем отфильтрованные объекты
        filtered_qs = self.filter(dto)

        # Агрегация сумм (это работает напрямую)
        aggregates = filtered_qs.aggregate(
            total_sum=Sum('total_sum_subcontract'),
            total_monthly=Sum('monthly_sum_subcontract'),
        )

        # Подсчет АК отдельным методом (Many-to-Many нельзя агрегировать просто так)
        total_aks = self._count_total_aks(filtered_qs)

        # Пагинация
        paginator = Paginator(filtered_qs, per_page)
        page_obj = paginator.get_page(dto.page)

        return SubcontractorReportResult(
            protection_objects=page_obj,
            total_objects=paginator.count,
            total_aks=total_aks,
            total_subcontract_sum=aggregates['total_sum'] or Decimal('0.00'),
            total_monthly_subcontract_sum=aggregates['total_monthly'] or Decimal('0.00'),
        )

    def has_active_filters(self, dto: SubcontractorFilterDTO) -> bool:
        """Проверяет, заданы ли фильтры для поиска."""
        return bool(
            dto.subcontractor_id or
            dto.subcontractor_search or
            dto.work_ids or
            dto.executor_ids
        )

    def get_filter_choices(self) -> dict:
        """
        Получает варианты выбора для фильтров.

        Returns:
            Словарь с доступными исполнителями и видами работ
        """
        available_executor_ids = self._get_available_executor_ids()

        executors = Company.objects.filter(
            id__in=available_executor_ids
        ).order_by('name')

        # Виды работ только для долгосрочного ТО лицензиата
        works = Work.objects.filter(
            work_type=Work.WorkType.LONGTERM_TO_LICENSEE,
            is_active=True,
        ).order_by('name')

        return {
            'executors': executors,
            'works': works,
        }

    def get_context_data(
            self,
            dto: SubcontractorFilterDTO,
            result: Optional[SubcontractorReportResult] = None
    ) -> dict:
        """
        Формирует контекст для шаблона.

        Args:
            dto: Параметры фильтрации
            result: Результат отчета (если есть)

        Returns:
            Словарь контекста для рендеринга шаблона
        """
        context = {
            # Параметры фильтров
            'subcontractor_id': dto.subcontractor_id or '',
            'subcontractor_search': dto.subcontractor_search or '',
            'selected_executor_ids': dto.executor_ids,
            'selected_work_ids': dto.work_ids,

            # Варианты выбора
            **self.get_filter_choices(),

            # Флаги состояния
            'has_active_filters': self.has_active_filters(dto),
            'is_search_performed': result is not None,
        }

        if result:
            context.update({
                'protection_objects': result.protection_objects,
                'total_objects': result.total_objects,
                'total_aks': result.total_aks,
                'total_subcontract_sum': result.total_subcontract_sum,
                'total_monthly_subcontract_sum': result.total_monthly_subcontract_sum,
                'page_obj': result.protection_objects,  # Для совместимости с шаблоном пагинации
            })

        return context