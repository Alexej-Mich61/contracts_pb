#apps/audit/apps.py
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"

    def ready(self):
        print("APPS.AUDIT READY")  # ← должно появиться при старте
        import apps.audit.signals  # подцепляем сигналы
