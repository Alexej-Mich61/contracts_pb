# apps/chat/tasks.py
from celery import shared_task
from .services import OnlineStatusService


@shared_task
def update_online_statuses():
    """Обновить статусы онлайн (запускать каждую минуту)."""
    OnlineStatusService.update_all_statuses()