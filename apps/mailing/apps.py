# apps/mailing/apps.py
from django.apps import AppConfig


class MailingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mailing'
    verbose_name = 'Рассылка e-mail'