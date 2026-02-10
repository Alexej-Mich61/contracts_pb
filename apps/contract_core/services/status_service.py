# apps/contract_core/services/status_service.py
from django.utils import timezone



class ContractStatusCalculator:
    """
    Сервис для расчёта статуса договора на основе текущих данных.

    Не изменяет объекты, только возвращает вычисленный статус.
    Используется в save(), в celery-задачах, в формах и т.д.
    """

    @staticmethod
    def calculate_status(contract: 'Contract') -> str:
        """
        Вычисляет актуальный статус договора.

        Args:
            contract: экземпляр модели Contract

        Returns:
            строка из Contract.STATUS_CHOICES (например, 'active', 'active_expires')
        """
        # Импортируем модели внутри метода — цикл не возникает
        from apps.contract_core.models import Contract, ContractSettings

        if contract.date_start is None or contract.date_end is None:
            return Contract.STATUS_PENDING

        settings = ContractSettings.get_settings()  # ← вот это правильный вызов

        today = timezone.now().date()

        # Защита от отрицательных/будущих дней
        days_left = (
            (contract.date_end - today).days
            if contract.date_end >= today
            else -1
        )

        # 1. Долгосрочный ТО (лицензиат)
        if contract.type == Contract.Type.LONGTERM_TO_LICENSEE:
            if today < contract.date_start:
                return Contract.STATUS_PENDING

            if today > contract.date_end:
                return Contract.STATUS_COMPLETED

            # внутри срока
            if days_left <= settings.days_before_expires:
                return Contract.STATUS_ACTIVE_EXPIRES

            return Contract.STATUS_ACTIVE

        # 2. Разовые договоры (лицензиат или лаборатория)
        if contract.type in (Contract.Type.ONEOFF_LICENSEE, Contract.Type.ONEOFF_LAB):
            if hasattr(contract, 'final_act') and contract.final_act.present:
                return Contract.STATUS_COMPLETED

            if today < contract.date_start:
                return Contract.STATUS_PENDING

            if today > contract.date_end:
                return Contract.STATUS_ACTIVE_EXPIRED

            # внутри срока
            if days_left <= settings.days_before_expires:
                return Contract.STATUS_ACTIVE_EXPIRES

            return Contract.STATUS_ACTIVE

        # fallback — если тип неизвестен или не обработан
        return Contract.STATUS_PENDING
