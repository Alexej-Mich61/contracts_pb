# apps/contract_core/services/works_sum_report_service.py
from typing import Dict, List, Optional
from collections import defaultdict
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone

from apps.contract_core.models import Company, Contract


class CompanyReportData:
    """DTO для данных отчета по компании."""

    def __init__(self):
        self.company: Optional[Company] = None
        self.roles: List[str] = []
        self.sections: Dict[str, Dict] = {}
        self.total_count: int = 0
        self.total_sum: Decimal = Decimal('0.00')
        self.total_monthly: Decimal = Decimal('0.00')


class WorksSumReportService:
    """
    Сервис для формирования отчета по работам и суммам.
    """

    CONTRACT_TYPE_MAPPING = {
        Contract.Type.ONEOFF_LICENSEE: {
            'section_key': 'oneoff_licensee',
            'section_name': 'Разовые (лицензиат)',
        },
        Contract.Type.LONGTERM_TO_LICENSEE: {
            'section_key': 'longterm_to_licensee',
            'section_name': 'Долгосрочные (лицензиат)',
        },
        Contract.Type.ONEOFF_LAB: {
            'section_key': 'oneoff_lab',
            'section_name': 'Разовые (лаборатория)',
        },
    }

    ACTIVE_STATUSES = [
        Contract.STATUS_ACTIVE,
        Contract.STATUS_ACTIVE_EXPIRES,
        Contract.STATUS_ACTIVE_EXPIRED,
    ]

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

    def get_company_active_contracts(self, company: Company):
        """Получает действующие договоры компании."""
        return Contract.objects.filter(
            executor=company,
            status__in=self.ACTIVE_STATUSES,
            is_trash=False,
            is_archived=False
        ).select_related('work').order_by('work__name')

    def _get_company_roles_display(self, company: Company) -> List[str]:
        """Возвращает список ролей компании."""
        roles = []
        if company.is_licensee:
            roles.append('лицензиат')
        if company.is_laboratory:
            roles.append('лаборатория')
        return roles

    def _aggregate_contracts_by_work(self, contracts) -> Dict:
        """
        Агрегирует договоры по виду работ.
        Считает: общую сумму (total_sum + monthly_sum) и отдельно monthly_sum.
        """
        work_stats = defaultdict(lambda: {
            'count': 0,
            'sum': Decimal('0.00'),
            'monthly': Decimal('0.00')
        })

        for contract in contracts:
            work_name = contract.work.name if contract.work else 'Не указано'

            # Общая сумма = total_sum + monthly_sum
            total = (contract.total_sum or Decimal('0.00')) + (contract.monthly_sum or Decimal('0.00'))
            # Сумма в месяц = monthly_sum
            monthly = contract.monthly_sum or Decimal('0.00')

            work_stats[work_name]['count'] += 1
            work_stats[work_name]['sum'] += total
            work_stats[work_name]['monthly'] += monthly

        return dict(work_stats)

    def build_company_report(self, company: Company) -> CompanyReportData:
        """Строит данные отчета для одной компании."""
        report_data = CompanyReportData()
        report_data.company = company
        report_data.roles = self._get_company_roles_display(company)

        contracts = self.get_company_active_contracts(company)

        contracts_by_type = defaultdict(list)
        for contract in contracts:
            contracts_by_type[contract.type].append(contract)

        for contract_type, mapping in self.CONTRACT_TYPE_MAPPING.items():
            if contract_type not in contracts_by_type:
                continue

            section_contracts = contracts_by_type[contract_type]
            work_stats = self._aggregate_contracts_by_work(section_contracts)

            section_total_count = sum(s['count'] for s in work_stats.values())
            section_total_sum = sum(s['sum'] for s in work_stats.values())
            section_total_monthly = sum(s['monthly'] for s in work_stats.values())

            report_data.sections[mapping['section_key']] = {
                'name': mapping['section_name'],
                'work_types': work_stats,
                'total_count': section_total_count,
                'total_sum': section_total_sum,
                'total_monthly': section_total_monthly,
            }

            report_data.total_count += section_total_count
            report_data.total_sum += section_total_sum
            report_data.total_monthly += section_total_monthly

        return report_data

    def generate_report(self) -> Dict:
        """Генерирует полный отчет."""
        companies = self.get_companies_queryset()
        companies_data = []

        for company in companies:
            company_report = self.build_company_report(company)
            if company_report.total_count > 0:
                companies_data.append(company_report)

        return {
            'report_date': self.report_date,
            'companies_data': companies_data,
        }