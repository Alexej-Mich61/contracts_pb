#apps/contract_core/apps.py
from django.apps import AppConfig # основной

import os
import sys
import threading
import time
import logging

import schedule # библиотека schedule для планировщика задач
from django.utils import timezone

logger = logging.getLogger("contract_core.scheduler")


# class ContractCoreConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'apps.contract_core'
#
#     def ready(self):
#         import apps.contract_core.signals  # ← подключаем сигналы

# //////////////////////////////////// обновление статусов по расписанию
class ContractCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contract_core"
    verbose_name = "Договоры"

    def ready(self):
        # Отсечь reloader-процесс Django (только рабочий процесс runserver)
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        # Защита от повторного вызова ready() в одном процессе
        if any(t.name == "contract_scheduler" for t in threading.enumerate()):
            return

        def scheduler_loop():
            # --- Регистрация задачи --- ВРЕМЯ ВЫПОЛНЕНИЯ
            schedule.every().day.at("02:00").do(_update_all_contract_statuses) # указать время выполнения

            logger.info("Планировщик обновления статусов договоров запущен (ежедневно в 02:00)")
            print("[Scheduler] Планировщик обновления статусов договоров запущен (02:00)")

            while True:
                try:
                    schedule.run_pending()
                except Exception:
                    logger.exception("Ошибка в планировщике")
                time.sleep(60)

        thread = threading.Thread(
            target=scheduler_loop,
            name="contract_scheduler",
            daemon=True,
        )
        thread.start()


def _update_all_contract_statuses():
    """
    Ежедневная задача: пересчёт статусов.
    Импорты внутри функции, чтобы не было проблем с AppRegistryNotReady.
    """
    from django.db import close_old_connections
    from apps.contract_core.models import Contract
    from apps.contract_core.services.status_service import ContractStatusCalculator

    close_old_connections()

    try:
        qs = Contract.objects.filter(is_trash=False, is_archived=False)
        total = qs.count()

        to_update = []
        updated_count = 0
        now = timezone.now()

        for contract in qs.iterator(chunk_size=200):
            new_status = ContractStatusCalculator.calculate_status(contract)

            if new_status != contract.status:
                contract.status = new_status
                contract.updated_at = now
                to_update.append(contract)
                updated_count += 1

            if len(to_update) >= 200:
                Contract.objects.bulk_update(to_update, ["status", "updated_at"], batch_size=200)
                to_update.clear()

        if to_update:
            Contract.objects.bulk_update(to_update, ["status", "updated_at"], batch_size=200)

        msg = (
            f"[{now:%Y-%m-%d %H:%M:%S}] Статусы обновлены: "
            f"изменено {updated_count} из {total}"
        )
        logger.info(msg)
        print(msg)

    except Exception:
        logger.exception("Ошибка при ежедневном обновлении статусов договоров")
    finally:
        close_old_connections()

