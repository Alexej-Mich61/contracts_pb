# apps/chat/services.py
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Dialogue, UserOnlineStatus

User = get_user_model()


class DialogueService:
    """Сервис для работы с диалогами."""

    @staticmethod
    def get_or_create_dialogue(user1, user2):
        """Получить или создать диалог между двумя пользователями."""
        # Нормализуем порядок (меньший ID всегда participant1)
        if user1.id > user2.id:
            user1, user2 = user2, user1

        dialogue, created = Dialogue.objects.get_or_create(
            participant1=user1,
            participant2=user2
        )
        return dialogue

    @staticmethod
    def get_user_dialogues(user):
        """Получить все диалоги пользователя."""
        return Dialogue.objects.filter(
            Q(participant1=user) | Q(participant2=user)
        ).order_by("-updated_at")

    @staticmethod
    def get_total_unread_count(user):
        """Общее количество непрочитанных сообщений."""
        count = 0
        dialogues = DialogueService.get_user_dialogues(user)
        for dialogue in dialogues:
            count += dialogue.get_unread_count(user)
        return count


class OnlineStatusService:
    """Сервис для управления статусами онлайн."""

    @staticmethod
    def ping(user):
        """Обновить статус пользователя."""
        status, _ = UserOnlineStatus.objects.get_or_create(user=user)
        return status.ping()

    @staticmethod
    def update_all_statuses():
        """Обновить статусы всех пользователей (для celery таски)."""
        for status in UserOnlineStatus.objects.all():
            status.update_status()

    @staticmethod
    def is_user_online(user):
        """Проверить, онлайн ли пользователь."""
        try:
            status = user.online_status
            return status.update_status()
        except UserOnlineStatus.DoesNotExist:
            return False