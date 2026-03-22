# apps/contract_core/services/signing_stage_report_service.py
"""
Сервис для формирования отчётов по стадиям подписания договоров.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import timedelta
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.contract_core.models import (
    Contract, Company, SigningStage, SigningStageControlSettings
)

User = get_user_model()


@dataclass(frozen=True)
class StageCount:
    """DTO для пары (стадия, количество, просроченные)."""
    stage: SigningStage
    count: int
    overdue_count: int  # Новое поле


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
        self._control_settings: Optional[SigningStageControlSettings] = None
        self._cutoff_date: Optional[timezone.datetime] = None

    def get_control_settings(self) -> SigningStageControlSettings:
        """Lazy-load настроек контроля сроков."""
        if self._control_settings is None:
            self._control_settings = SigningStageControlSettings.get_settings()
        return self._control_settings

    def get_control_days(self) -> int:
        """Возвращает количество дней для контроля."""
        return self.get_control_settings().control_days

    def get_cutoff_date(self) -> timezone.datetime:
        """Возвращает дату-отсечку для определения просроченных договоров."""
        if self._cutoff_date is None:
            days = self.get_control_days()
            self._cutoff_date = timezone.now() - timedelta(days=days)
        return self._cutoff_date

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
        """
        if user.is_superuser:
            return list(Company.objects.filter(
                Q(is_licensee=True) | Q(is_laboratory=True)
            ).distinct().order_by('name'))

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
        """Строит список пар (стадия, количество, просроченные)."""
        slug_to_data = self._aggregate_stage_counts(base_filter)

        return [
            StageCount(
                stage=stage,
                count=slug_to_data.get(stage.slug, {}).get('count', 0),
                overdue_count=slug_to_data.get(stage.slug, {}).get('overdue_count', 0)
                if not stage.is_final else 0
            )
            for stage in self.get_all_stages()
        ]

    def _aggregate_stage_counts(self, base_filter: Q) -> Dict[str, Dict[str, int]]:
        """
        Агрегирует количество договоров по стадиям и количество просроченных.

        Просроченными считаются договоры на нефинальных стадиях,
        дата изменения которых раньше контрольной даты.
        """
        cutoff_date = self.get_cutoff_date()

        # Условие для просроченных: не финальная стадия и changed_at раньше cutoff
        overdue_filter = Q(
            signing_stage__stage__is_final=False,
            signing_stage__changed_at__lt=cutoff_date
        )

        stage_stats = Contract.objects.filter(base_filter).values(
            'signing_stage__stage__slug'
        ).annotate(
            count=Count('id'),
            overdue_count=Count('id', filter=overdue_filter)
        )

        return {
            stat['signing_stage__stage__slug']: {
                'count': stat['count'],
                'overdue_count': stat['overdue_count'] or 0
            }
            for stat in stage_stats
            if stat['signing_stage__stage__slug']
        }
