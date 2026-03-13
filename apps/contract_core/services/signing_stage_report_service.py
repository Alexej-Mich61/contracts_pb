# apps/contract_core/services/signing_stage_report_service.py
"""
Сервис для формирования отчётов по стадиям подписания договоров.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

from apps.contract_core.models import Contract, Company, SigningStage

User = get_user_model()


@dataclass(frozen=True)
class StageCount:
    """DTO для пары (стадия, количество)."""
    stage: SigningStage
    count: int


@dataclass(frozen=True)
class ContractTypeStats:
    """DTO для статистики по типу договора."""
    type_label: str
    total: int
    stage_counts: List[StageCount]


@dataclass(frozen=True)
class CompanyRoleData:
    """DTO для данных роли компании."""
    role_name: str
    contract_types: List[ContractTypeStats]


@dataclass(frozen=True)
class CompanyReportData:
    """DTO для данных компании в отчёте."""
    company: Company
    roles: List[CompanyRoleData]


class SigningStageReportService:
    """
    Сервис формирования отчёта по стадиям подписания.
    """

    _ROLE_CONFIG: Dict[str, List[Tuple[str, str]]] = {
        'licensee': [
            (Contract.Type.ONEOFF_LICENSEE, 'Разовый (лицензиат)'),
            (Contract.Type.LONGTERM_TO_LICENSEE, 'Долгосрочный ТО (лицензиат)'),
        ],
        'laboratory': [
            (Contract.Type.ONEOFF_LAB, 'Разовый (лаборатория)'),
        ],
    }

    _ACTIVE_STATUSES = [
        Contract.STATUS_ACTIVE,
        Contract.STATUS_ACTIVE_EXPIRES,
        Contract.STATUS_ACTIVE_EXPIRED,
    ]

    def __init__(self):
        self._all_stages: Optional[List[SigningStage]] = None

    def get_report_data(self, user: User) -> List[CompanyReportData]:
        """
        Основной метод получения данных отчёта.

        - Суперпользователь видит ВСЕ компании-лицензиаты и лаборатории
        - Обычный пользователь видит только свои компании (где он сотрудник)
        """
        companies = self._get_companies_for_user(user)

        return [
            self._build_company_data(company)
            for company in companies
            if self._build_company_data(company)
        ]

    def _get_companies_for_user(self, user: User) -> List[Company]:
        """
        Получает список компаний в зависимости от прав пользователя.

        Args:
            user: Текущий пользователь

        Returns:
            Список компаний для отчёта
        """
        # Суперпользователь видит все компании-исполнители
        if user.is_superuser:
            return list(Company.objects.filter(
                Q(is_licensee=True) | Q(is_laboratory=True)
            ).distinct().order_by('name'))

        # Обычный пользователь видит только свои компании
        return list(Company.objects.filter(
            employees__user=user,
            employees__is_active=True
        ).distinct())

    def get_all_stages(self) -> List[SigningStage]:
        """Получает все стадии подписания."""
        if self._all_stages is None:
            self._all_stages = list(SigningStage.objects.all().order_by('order'))
        return self._all_stages

    def _build_company_data(self, company: Company) -> Optional[CompanyReportData]:
        """Строит данные отчёта для компании."""
        roles_data = self._build_roles_data(company)

        if not roles_data:
            return None

        return CompanyReportData(
            company=company,
            roles=roles_data
        )

    def _build_roles_data(self, company: Company) -> List[CompanyRoleData]:
        """Строит данные по всем ролям компании."""
        roles = []

        if company.is_licensee:
            roles.append(self._build_single_role_data(company, 'licensee', 'Лицензиат МЧС'))

        if company.is_laboratory:
            roles.append(self._build_single_role_data(company, 'laboratory', 'Лаборатория'))

        return roles

    def _build_single_role_data(
            self,
            company: Company,
            role_key: str,
            role_name: str
    ) -> CompanyRoleData:
        """Строит данные для одной роли."""
        contract_types_data = [
            self._build_contract_type_stats(company, type_code, type_label)
            for type_code, type_label in self._ROLE_CONFIG[role_key]
        ]

        return CompanyRoleData(
            role_name=role_name,
            contract_types=contract_types_data
        )

    def _build_contract_type_stats(
            self,
            company: Company,
            contract_type: str,
            type_label: str
    ) -> ContractTypeStats:
        """Собирает статистику по типу договора."""
        base_filter = self._build_base_filter(company, contract_type)
        total = Contract.objects.filter(base_filter).count()
        stage_counts = self._build_stage_counts_list(base_filter)

        return ContractTypeStats(
            type_label=type_label,
            total=total,
            stage_counts=stage_counts
        )

    def _build_base_filter(self, company: Company, contract_type: str) -> Q:
        """Базовый фильтр для актуальных договоров."""
        return Q(
            executor=company,
            type=contract_type,
            is_trash=False,
            is_archived=False,
            status__in=self._ACTIVE_STATUSES
        )

    def _build_stage_counts_list(self, base_filter: Q) -> List[StageCount]:
        """Строит список пар (стадия, количество)."""
        slug_to_count = self._aggregate_stage_counts(base_filter)

        return [
            StageCount(stage=stage, count=slug_to_count.get(stage.slug, 0))
            for stage in self.get_all_stages()
        ]

    def _aggregate_stage_counts(self, base_filter: Q) -> Dict[str, int]:
        """Агрегирует количество договоров по стадиям."""
        stage_stats = Contract.objects.filter(base_filter).values(
            'signing_stage__stage__slug'
        ).annotate(count=Count('id'))

        return {
            stat['signing_stage__stage__slug']: stat['count']
            for stat in stage_stats
            if stat['signing_stage__stage__slug']
        }