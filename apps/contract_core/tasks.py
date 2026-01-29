# apps/contract_core/tasks.py
from celery import shared_task
from apps.contract_core.models import Contract
from apps.contract_core.services.status_service import ContractStatusCalculator
from apps.contract_core.models import ContractSettings


"""
Celery-задачи для периодического обновления статусов договоров.
Запускаются по расписанию (обычно в 02:00 и 03:00).
"""


@shared_task
def update_longterm_contracts_status():
    """
    Пересчитывает статусы всех долгосрочных договоров ТО (лицензиат).
    Запускается обычно в 02:00.

    Возвращает строку для логов Celery.
    """
    settings = ContractSettings.get_settings()  # единый способ получения настроек

    qs = Contract.objects.filter(
        type=Contract.Type.LONGTERM_TO_LICENSEE,
        is_trash=False,
        is_archived=False,
        date_start__isnull=False,
        date_end__isnull=False,
    ).only(
        'id', 'status', 'type', 'date_start', 'date_end', 'final_act_present'
    )

    updated_count = 0

    for contract in qs.iterator():
        new_status = ContractStatusCalculator.calculate_status(contract)
        if new_status != contract.status:
            contract.status = new_status
            contract.save(update_fields=['status'])
            updated_count += 1

    result = f"Долгосрочные ТО: обновлено {updated_count} из {qs.count()} договоров"
    print(result)  # для отладки и логов
    return result


@shared_task
def update_oneoff_contracts_status():
    """
    Пересчитывает статусы всех разовых договоров (лицензиат + лаборатория).
    Запускается обычно в 03:00.

    Возвращает строку для логов Celery.
    """
    settings = ContractSettings.get_settings()

    qs = Contract.objects.filter(
        type__in=(
            Contract.Type.ONEOFF_LICENSEE,
            Contract.Type.ONEOFF_LAB
        ),
        is_trash=False,
        is_archived=False,
        date_start__isnull=False,
        date_end__isnull=False,
    ).only(
        'id', 'status', 'type', 'date_start', 'date_end', 'final_act_present'
    )

    updated_count = 0

    for contract in qs.iterator():
        new_status = ContractStatusCalculator.calculate_status(contract)
        if new_status != contract.status:
            contract.status = new_status
            contract.save(update_fields=['status'])
            updated_count += 1

    result = f"Разовые договоры: обновлено {updated_count} из {qs.count()} договоров"
    print(result)
    return result


@shared_task
def update_all_contract_statuses():
    """
    Объединяющая задача — обновляет статусы всех типов договоров.
    Можно использовать вместо двух отдельных задач.
    """
    longterm_result = update_longterm_contracts_status.delay().get()
    oneoff_result = update_oneoff_contracts_status.delay().get()

    combined = f"{longterm_result}\n{oneoff_result}"
    print(combined)
    return combined