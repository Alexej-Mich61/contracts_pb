from django.db.models import Q, Count
from django.contrib.auth import get_user_model

from ..models import (
    Contract, Company, Work, Region, District, SigningStage,
    ProtectionObject, Ak, FinalAct, InterimAct
)

User = get_user_model()


class ContractFilterService:
    """Сервис фильтрации договоров"""

    CONTRACT_TO_WORK_TYPE = {
        'oneoff_licensee': 'work_oneoff_licensee',
        'longterm_to_licensee': 'work_longterm_to_licensee',
        'oneoff_lab': 'work_oneoff_lab',
    }

    def __init__(self, request, queryset=None):
        self.request = request
        self.params = request.GET
        # Сохраняем базовый queryset (уже с фильтрацией по правам доступа)
        self.base_queryset = queryset

    def filter(self):
        """Применить все фильтры"""
        # Используем переданный queryset или берем все (для обратной совместимости)
        if self.base_queryset is not None:
            queryset = self.base_queryset
        else:
            queryset = Contract.objects.all()

        queryset = self._filter_by_location(queryset)
        queryset = self._filter_by_type(queryset)
        queryset = self._filter_by_status(queryset)
        queryset = self._filter_by_search(queryset)
        queryset = self._filter_by_date_range(queryset)
        queryset = self._filter_by_signing_stage(queryset)
        queryset = self._filter_by_region(queryset)
        queryset = self._filter_by_objects(queryset)
        queryset = self._filter_by_ak(queryset)
        queryset = self._filter_by_acts(queryset)
        queryset = self._filter_by_file(queryset)
        queryset = self._filter_by_author(queryset)

        queryset = self._optimize_queryset(queryset)

        return queryset.order_by('-created_at').distinct()

    def _optimize_queryset(self, queryset):
        """Оптимизация запросов"""
        return queryset.select_related(
            'customer',
            'executor',
            'work',
            'signing_stage__stage',
            'creator',
            'updater'
        ).prefetch_related(
            'contract_objects__district__region',
            'contract_objects__subcontractor',
            'contract_objects__aks',
            'final_act',
            'interim_acts',
            'system_checks__system_type'
        ).annotate(
            object_count=Count('contract_objects', distinct=True),
            ak_count=Count('contract_objects__aks', distinct=True)
        )

    def _filter_by_location(self, queryset):
        """Фильтр по расположению"""
        location = self.params.get('location', 'active')

        if location == 'active':
            queryset = queryset.filter(is_trash=False, is_archived=False)
        elif location == 'archived':
            queryset = queryset.filter(is_archived=True)
        elif location == 'trash':
            queryset = queryset.filter(is_trash=True)

        return queryset

    def _filter_by_type(self, queryset):
        """Фильтр по типу договора и работе"""
        contract_type = self.params.get('contract_type')
        work_id = self.params.get('work')

        if contract_type:
            queryset = queryset.filter(type=contract_type)
            if not work_id:
                work_type = self.CONTRACT_TO_WORK_TYPE.get(contract_type)
                if work_type:
                    queryset = queryset.filter(work__work_type=work_type)

        if work_id:
            queryset = queryset.filter(work_id=work_id)

        return queryset

    def _filter_by_status(self, queryset):
        """Фильтр по статусу"""
        statuses = self.params.getlist('status')
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        return queryset

    def _filter_by_search(self, queryset):
        """Комплексный поиск"""
        contract_id = self.params.get('contract_id')
        if contract_id:
            queryset = queryset.filter(pk=contract_id)

        number = self.params.get('number')
        if number:
            queryset = queryset.filter(number__icontains=number)

        customer_q = self.params.get('customer')
        if customer_q:
            queryset = queryset.filter(
                Q(customer__name__icontains=customer_q) |
                Q(customer__inn__icontains=customer_q)
            )

        executor_q = self.params.get('executor')
        if executor_q:
            queryset = queryset.filter(
                Q(executor__name__icontains=executor_q) |
                Q(executor__inn__icontains=executor_q)
            )

        subcontractor_q = self.params.get('subcontractor')
        if subcontractor_q:
            queryset = queryset.filter(
                Q(contract_objects__subcontractor__name__icontains=subcontractor_q) |
                Q(contract_objects__subcontractor__inn__icontains=subcontractor_q)
            )

        return queryset

    def _filter_by_date_range(self, queryset):
        """Фильтр по диапазону дат действия"""
        date_from = self.params.get('date_from')
        date_to = self.params.get('date_to')

        if date_from:
            queryset = queryset.filter(date_start__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_end__lte=date_to)

        return queryset

    def _filter_by_signing_stage(self, queryset):
        """Фильтр по текущей стадии подписания"""
        is_final = self.params.get('is_final')
        if is_final == 'yes':
            queryset = queryset.filter(signing_stage__stage__is_final=True)
        elif is_final == 'no':
            queryset = queryset.filter(
                Q(signing_stage__isnull=True) |
                Q(signing_stage__stage__is_final=False)
            )

        stages = self.params.getlist('signing_stages')
        if stages:
            queryset = queryset.filter(signing_stage__stage_id__in=stages)

        return queryset

    def _filter_by_region(self, queryset):
        """Фильтр по региону и району"""
        region_id = self.params.get('region')
        district_id = self.params.get('district')

        if district_id:
            queryset = queryset.filter(contract_objects__district_id=district_id)
        elif region_id:
            queryset = queryset.filter(contract_objects__district__region_id=region_id)

        return queryset

    def _filter_by_objects(self, queryset):
        """Фильтр по объектам защиты"""
        obj_name = self.params.get('object_name')
        if obj_name:
            queryset = queryset.filter(contract_objects__name__icontains=obj_name)

        obj_address = self.params.get('object_address')
        if obj_address:
            queryset = queryset.filter(contract_objects__address__icontains=obj_address)

        has_subcontractor = self.params.get('has_subcontractor')
        if has_subcontractor == 'yes':
            queryset = queryset.filter(contract_objects__subcontractor__isnull=False)
        elif has_subcontractor == 'no':
            queryset = queryset.filter(contract_objects__subcontractor__isnull=True)

        has_ak = self.params.get('has_ak')
        if has_ak == 'yes':
            queryset = queryset.filter(contract_objects__aks__isnull=False)
        elif has_ak == 'no':
            queryset = queryset.filter(contract_objects__aks__isnull=True)

        return queryset

    def _filter_by_ak(self, queryset):
        """Фильтр по АК"""
        ak_id = self.params.get('ak_id')
        if ak_id:
            queryset = queryset.filter(contract_objects__aks__id=ak_id)

        ak_number = self.params.get('ak_number')
        if ak_number:
            queryset = queryset.filter(contract_objects__aks__number=ak_number)

        ak_name = self.params.get('ak_name')
        if ak_name:
            queryset = queryset.filter(contract_objects__aks__name__icontains=ak_name)

        ak_address = self.params.get('ak_address')
        if ak_address:
            queryset = queryset.filter(contract_objects__aks__address__icontains=ak_address)

        return queryset

    def _filter_by_acts(self, queryset):
        """Фильтр по актам"""
        from django.db.models import Exists, OuterRef

        # Итоговый акт (OneToOne)
        has_final_act = self.params.get('has_final_act')
        if has_final_act == 'yes':
            queryset = queryset.filter(final_act__isnull=False)
        elif has_final_act == 'no':
            queryset = queryset.filter(final_act__isnull=True)

        # Файл итогового акта
        has_final_act_file = self.params.get('has_final_act_file')
        if has_final_act_file == 'yes':
            queryset = queryset.filter(
                final_act__isnull=False,
                final_act__file__isnull=False,
                final_act__file__gt=''
            )
        elif has_final_act_file == 'no':
            queryset = queryset.filter(
                Q(final_act__isnull=True) |
                Q(final_act__file__isnull=True) |
                Q(final_act__file='')
            )

        # Промежуточные акты (ForeignKey с related_name='interim_acts')
        has_interim_acts = self.params.get('has_interim_acts')
        if has_interim_acts == 'yes':
            queryset = queryset.annotate(
                has_interim=Exists(
                    InterimAct.objects.filter(contract=OuterRef('pk'))
                )
            ).filter(has_interim=True)
        elif has_interim_acts == 'no':
            queryset = queryset.annotate(
                has_interim=Exists(
                    InterimAct.objects.filter(contract=OuterRef('pk'))
                )
            ).filter(has_interim=False)

        return queryset

    def _filter_by_file(self, queryset):
        """Фильтр по файлу договора"""
        has_file = self.params.get('has_file')
        if has_file == 'yes':
            queryset = queryset.filter(file__isnull=False, file__gt='')
        elif has_file == 'no':
            queryset = queryset.filter(Q(file__isnull=True) | Q(file=''))
        return queryset

    def _filter_by_author(self, queryset):
        """Поиск по автору"""
        author = self.params.get('author')
        if author:
            queryset = queryset.filter(
                Q(creator__username__icontains=author) |
                Q(creator__first_name__icontains=author) |
                Q(creator__last_name__icontains=author) |
                Q(updater__username__icontains=author) |
                Q(updater__first_name__icontains=author) |
                Q(updater__last_name__icontains=author)
            )
        return queryset

    @staticmethod
    def get_filter_choices():
        """Данные для формы фильтра"""
        return {
            'contract_types': Contract.Type.choices,
            'works': Work.objects.filter(is_active=True).values('id', 'name', 'work_type'),
            'statuses': Contract.STATUS_CHOICES,
            'regions': Region.objects.all().values('id', 'name'),
            'signing_stages': SigningStage.objects.all().values('id', 'name', 'is_final', 'order'),
        }

    @staticmethod
    def get_works_by_contract_type(contract_type):
        """Получить работы по типу договора"""
        if not contract_type:
            return Work.objects.filter(is_active=True)

        work_type = ContractFilterService.CONTRACT_TO_WORK_TYPE.get(contract_type)
        if work_type:
            return Work.objects.filter(is_active=True, work_type=work_type)

        return Work.objects.filter(is_active=True)

    @staticmethod
    def get_districts_by_region(region_id):
        """Получить районы по региону"""
        if region_id:
            return District.objects.filter(region_id=region_id)
        return District.objects.all()