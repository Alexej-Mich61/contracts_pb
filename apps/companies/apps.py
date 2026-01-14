# apps/companies/apps.py
from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.companies'          # ← полный путь
    verbose_name = 'Организации'