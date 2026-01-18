# apps/chat/models.py
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models

User = get_user_model()


class UserChatSettings(models.Model):
    """Глобальные настройки звука/громкости для пользователя."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="chat_settings")
    # глобальный выключатель
    is_sound_enabled = models.BooleanField("Звук включён", default=True)
    # громкость 0-100
    volume = models.PositiveSmallIntegerField(
        "Громкость уведомлений",
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # файл-звук по умолчанию (кладёте в media/notifications/)
    default_sound = models.FileField(
        "Файл звука по умолчанию",
        upload_to="notifications/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["mp3", "wav", "ogg"])],
    )

    class Meta:
        verbose_name = "Настройки чата пользователя"
        verbose_name_plural = "Настройки чатов пользователей"

    def __str__(self):
        return f"Звук {self.user} ({'ON' if self.is_sound_enabled else 'OFF'}, {self.volume}%)"


class Dialogue(models.Model):
    participant1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dialogues_as_1")
    participant2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dialogues_as_2")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # звук для этого диалога
    is_sound_on = models.BooleanField("Звук в диалоге", default=True)
    custom_sound = models.FileField(
        "Свой звук диалога",
        upload_to="notifications/dialogues/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["mp3", "wav", "ogg"])],
    )

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"
        constraints = [
            models.UniqueConstraint(
                fields=["participant1", "participant2"],
                name="%(app_label)s_%(class)s_unique_pair",
            ),
            models.CheckConstraint(
                check=~models.Q(participant1=models.F("participant2")),
                name="%(app_label)s_%(class)s_no_self_talk",
            ),
        ]


class Message(models.Model):
    dialogue = models.ForeignKey(Dialogue, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField("Текст сообщения")
    is_read = models.BooleanField("Прочитано", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}"

    # уведомление-звук для этого конкретного сообщения
    def play_sound_info(self, for_user: User):
        """
        Возвращает словарь, который фронт использует для проигрывания звука:
        - file_url   – URL файла (media/...)
        - volume     – 0-100
        - enabled    – проигрывать ли вообще
        """
        settings, _ = UserChatSettings.objects.get_or_create(user=for_user)
        if not settings.is_sound_enabled:
            return {"enabled": False}

        dialogue = self.dialogue
        if not dialogue.is_sound_on:
            return {"enabled": False}

        # приоритет: 1) свой звук диалога, 2) глобальный, 3) молчать
        sound_file = (
            dialogue.custom_sound
            if dialogue.custom_sound
            else settings.default_sound
        )
        if not sound_file:
            return {"enabled": False}

        return {
            "enabled": True,
            "file_url": sound_file.url,
            "volume": settings.volume,
        }