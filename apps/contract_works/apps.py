#apps/contract_works/apps.py
from django.apps import AppConfig

class ContractWorksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contract_works'   # ← полный путь
    verbose_name = 'Виды работ'