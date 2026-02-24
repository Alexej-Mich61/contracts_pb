# apps/contract_core/services/history_service.py
from django.db.models import Q, QuerySet
from django.contrib.contenttypes.models import ContentType
from auditlog.models import LogEntry

from ..models import (
    Contract, FinalAct, InterimAct, ContractSigningStage,
    ContractSystemCheck, ProtectionObject, Ak
)


class ContractHistoryService:
    """Сервис для получения истории изменений договора и связанных объектов"""

    def __init__(self, contract: Contract):
        self.contract = contract
        self._content_types = None

    def get_all_logs(self) -> QuerySet[LogEntry]:
        """Получить все логи для договора и связанных объектов"""
        q_objects = self._build_query()

        return LogEntry.objects.filter(q_objects).select_related(
            'actor', 'content_type'
        ).order_by('-timestamp')

    def _build_query(self) -> Q:
        """Построить Q-объект для фильтрации логов"""
        contract_pk = str(self.contract.pk)

        # Получаем ContentType для всех моделей
        content_types = self._get_content_types()

        # Начинаем с самого договора
        q_objects = Q(
            content_type=content_types[Contract],
            object_id=contract_pk
        )

        # Добавляем связанные объекты
        q_objects |= self._get_final_act_query(content_types)
        q_objects |= self._get_interim_acts_query(content_types)
        q_objects |= self._get_signing_stage_query(content_types)
        q_objects |= self._get_system_checks_query(content_types)
        q_objects |= self._get_protection_objects_query(content_types)

        return q_objects

    def _get_content_types(self) -> dict:
        """Кэширование ContentType"""
        if self._content_types is None:
            self._content_types = ContentType.objects.get_for_models(
                Contract, FinalAct, InterimAct, ContractSigningStage,
                ContractSystemCheck, ProtectionObject, Ak
            )
        return self._content_types

    def _get_final_act_query(self, content_types: dict) -> Q:
        """Логи итогового акта"""
        try:
            final_act = FinalAct.objects.get(contract=self.contract)
            return Q(
                content_type=content_types[FinalAct],
                object_id=str(final_act.pk)
            )
        except FinalAct.DoesNotExist:
            return Q()

    def _get_interim_acts_query(self, content_types: dict) -> Q:
        """Логи промежуточных актов"""
        ids = InterimAct.objects.filter(
            contract=self.contract
        ).values_list('id', flat=True)

        if ids:
            return Q(
                content_type=content_types[InterimAct],
                object_id__in=[str(i) for i in ids]
            )
        return Q()

    def _get_signing_stage_query(self, content_types: dict) -> Q:
        """Логи стадии подписания"""
        try:
            stage = ContractSigningStage.objects.get(contract=self.contract)
            return Q(
                content_type=content_types[ContractSigningStage],
                object_id=str(stage.pk)
            )
        except ContractSigningStage.DoesNotExist:
            return Q()

    def _get_system_checks_query(self, content_types: dict) -> Q:
        """Логи проверок систем"""
        ids = ContractSystemCheck.objects.filter(
            contract=self.contract
        ).values_list('id', flat=True)

        if ids:
            return Q(
                content_type=content_types[ContractSystemCheck],
                object_id__in=[str(i) for i in ids]
            )
        return Q()

    def _get_protection_objects_query(self, content_types: dict) -> Q:
        """Логи объектов защиты и АК"""
        protection_ids = list(ProtectionObject.objects.filter(
            contract=self.contract
        ).values_list('id', flat=True))

        if not protection_ids:
            return Q()

        # Логи объектов защиты
        q = Q(
            content_type=content_types[ProtectionObject],
            object_id__in=[str(i) for i in protection_ids]
        )

        # Логи АК, связанных с этими объектами
        ak_ids = Ak.objects.filter(
            protection_objects__id__in=protection_ids
        ).values_list('id', flat=True).distinct()

        if ak_ids:
            q |= Q(
                content_type=content_types[Ak],
                object_id__in=[str(i) for i in ak_ids]
            )

        return q