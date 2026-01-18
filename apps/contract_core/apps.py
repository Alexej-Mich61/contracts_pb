#apps/contract_core/apps.py
from django.apps import AppConfig


class ContractCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contract_core'
    verbose_name = 'Базовый контракт'

    def ready(self):
        import apps.contract_core.signals

