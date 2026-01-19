# apps/contract_core/tasks.py
from celery import shared_task
from .models import Contract, ContractSettings

@shared_task
def update_longterm_contracts_status():
    settings = ContractSettings.objects.first()
    qs = (Contract.objects
          .filter(type=Contract.TYPE_LONGTERM_TO_LICENSEE,
                  is_trash=False,
                  is_archived=False)
          .select_related())
    for c in qs:
        c._recalc_status()
        c.save(update_fields=["status"])

@shared_task
def update_oneoff_contracts_status():
    settings = ContractSettings.objects.first()
    qs = (Contract.objects
          .filter(type__in=(Contract.TYPE_ONEOFF_LICENSEE,
                            Contract.TYPE_ONEOFF_LAB),
                  is_trash=False,
                  is_archived=False)
          .select_related())
    for c in qs:
        c._recalc_status()
        c.save(update_fields=["status"])