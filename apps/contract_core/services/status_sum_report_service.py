# apps/contract_core/services/status_sum_report_service.py
from typing import Dict, List, Optional
from collections import defaultdict
from decimal import Decimal
from django.db.models import Q, Sum, Count
from django.utils import timezone

from apps.contract_core.models import Company, Contract


class CompanyStatusReportData:
    """DTO для данных отчета по статусам."""

    def __init__(self):
        self.company: Optional[Company] = None
        self.roles: List[str] = []
        self.sections: Dict[str, Dict] = {}


class StatusSumReportService:
    """
    Сервис для формирования отчета по статусам и суммам.
    """

    CONTRACT_TYPE_MAPPING = {
        Contract.Type.ONEOFF_LICENSEE: {
            'section_key': 'oneoff_licensee',
            'section_name': 'Разовые (лицензиат)',
            'has_expired': True,
        },
        Contract.Type.LONGTERM_TO_LICENSEE: {
            'section_key': 'longterm_to_licensee',
            'section_name': 'Долгосрочные (лицензиат)',
            'has_expired': False,
        },
        Contract.Type.ONEOFF_LAB: {
            'section_key': 'oneoff_lab',
            'section_name': 'Разовые (лаборатория)',
            'has_expired': True,
        },
    }

    # Статусы для отчета (кроме pending)
    REPORT_STATUSES = {
        Contract.STATUS_COMPLETED: 'Завершен',
        Contract.STATUS_ACTIVE: 'Действует',
        Contract.STATUS_ACTIVE_EXPIRES: 'Истекает',
        Contract.STATUS_ACTIVE_EXPIRED: 'Истёк',
    }

    def __init__(self, user):
        self.user = user
        self.report_date = timezone.now()

    def get_companies_queryset(self):
        """Получает компании в зависимости от прав пользователя."""
        base_qs = Company.objects.filter(
            Q(is_licensee=True) | Q(is_laboratory=True)
        )

        if self.user.is_superuser or getattr(self.user, 'is_admin', False):
            return base_qs.distinct().order_by('name')

        return base_qs.filter(
            employees__user=self.user,
            employees__is_active=True
        ).distinct().order_by('name')

    def get_company_contracts(self, company: Company):
        """Получает неархивные договоры компании (не в корзине, не в архиве)."""
        return Contract.objects.filter(
            executor=company,
            is_trash=False,
            is_archived=False
        ).exclude(
            status=Contract.STATUS_PENDING
        ).select_related('work')

    def _get_company_roles_display(self, company: Company) -> List[str]:
        """Возвращает список ролей компании."""
        roles = []
        if company.is_licensee:
            roles.append('лицензиат')
        if company.is_laboratory:
            roles.append('лаборатория')
        return roles

    def _aggregate_by_status(self, contracts) -> Dict:
        """
        Агрегирует договоры по статусам.
        Возвращает: {status_key: {'count': int, 'sum': Decimal}}
        """
        stats = {key: {'count': 0, 'sum': Decimal('0.00')} for key in self.REPORT_STATUSES.keys()}
        stats['total'] = {'count': 0, 'sum': Decimal('0.00')}

        for contract in contracts:
            total = contract.total_sum or Decimal('0.00')

            stats['total']['count'] += 1
            stats['total']['sum'] += total

            if contract.status in stats:
                stats[contract.status]['count'] += 1
                stats[contract.status]['sum'] += total

        return stats

    def build_company_report(self, company: Company) -> CompanyStatusReportData:
        """Строит данные отчета для одной компании."""
        report_data = CompanyStatusReportData()
        report_data.company = company
        report_data.roles = self._get_company_roles_display(company)

        contracts = self.get_company_contracts(company)

        # Группируем по типам контрактов
        contracts_by_type = defaultdict(list)
        for contract in contracts:
            contracts_by_type[contract.type].append(contract)

        # Обрабатываем каждый тип
        for contract_type, mapping in self.CONTRACT_TYPE_MAPPING.items():
            if contract_type not in contracts_by_type:
                continue

            section_contracts = contracts_by_type[contract_type]
            status_stats = self._aggregate_by_status(section_contracts)

            # Определяем какие статусы показывать
            available_statuses = ['completed', 'active', 'active_expires']
            if mapping['has_expired']:
                available_statuses.append('active_expired')

            report_data.sections[mapping['section_key']] = {
                'name': mapping['section_name'],
                'has_expired': mapping['has_expired'],
                'stats': status_stats,
                'available_statuses': available_statuses,
            }

        return report_data

    def generate_report(self) -> Dict:
        """Генерирует полный отчет."""
        companies = self.get_companies_queryset()
        companies_data = []

        for company in companies:
            company_report = self.build_company_report(company)
            # Добавляем только если есть данные
            if company_report.sections:
                companies_data.append(company_report)

        return {
            'report_date': self.report_date,
            'companies_data': companies_data,
        }