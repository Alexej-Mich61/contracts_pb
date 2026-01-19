# config/celery.py
from celery import Celery
from celery.schedules import crontab
app = Celery("contracts_pb")
app.config_from_object("django.conf:settings", namespace="CELERY")

# читаем время из настроек
from apps.contract_core.models import ContractSettings
settings = ContractSettings.objects.first() or ContractSettings()

app.conf.beat_schedule = {
    "longterm-status": {
        "task": "apps.contract_core.tasks.update_longterm_contracts_status",
        "schedule": crontab(
            hour=settings.longterm_status_time.hour,
            minute=settings.longterm_status_time.minute,
        ),
    },
    "oneoff-status": {
        "task": "apps.contract_core.tasks.update_oneoff_contracts_status",
        "schedule": crontab(
            hour=settings.oneoff_status_time.hour,
            minute=settings.oneoff_status_time.minute,
        ),
    },
}