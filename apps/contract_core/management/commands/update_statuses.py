# apps/contract_core/management/commands/update_statuses.py
import logging

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger("contract_core.scheduler")


class Command(BaseCommand):
    help = "Пересчитать статусы всех активных договоров"

    def handle(self, *args, **options):
        from apps.contract_core.models import Contract
        from apps.contract_core.services.status_service import ContractStatusCalculator

        self.stdout.write("Запуск обновления статусов...")

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
            self.stdout.write(self.style.SUCCESS(msg))

        except Exception:
            logger.exception("Ошибка при обновлении статусов договоров")
            raise
        finally:
            close_old_connections()
