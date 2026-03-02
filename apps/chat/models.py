# apps/chat/models.py
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class GlobalChatSettings(models.Model):
    """Глобальные настройки чата (singleton)."""
    default_sound = models.FileField(
        "Звук уведомления по умолчанию",
        upload_to="notifications/global/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["mp3", "wav", "ogg"])],
        help_text="Звук, который будет использоваться для всех уведомлений по умолчанию",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Глобальные настройки чата"
        verbose_name_plural = "Глобальные настройки чата"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Глобальные настройки (обновлено: {self.updated_at})"


class UserChatSettings(models.Model):
    """Персональные настройки чата пользователя."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="chat_settings"
    )
    is_sound_enabled = models.BooleanField("Звук включён", default=True)
    volume = models.PositiveSmallIntegerField(
        "Громкость уведомлений",
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # Пользователь может загрузить свой звук, иначе используем глобальный
    custom_sound = models.FileField(
        "Персональный звук уведомления",
        upload_to="notifications/users/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["mp3", "wav", "ogg"])],
        help_text="Если не загружен - используется глобальный звук",
    )

    class Meta:
        verbose_name = "Настройки чата пользователя"
        verbose_name_plural = "Настройки чатов пользователей"

    def __str__(self):
        return f"{self.user} ({'ON' if self.is_sound_enabled else 'OFF'}, {self.volume}%)"

    def get_sound_url(self):
        """Возвращает URL звука для пользователя (персональный или глобальный)."""
        if self.custom_sound:
            return self.custom_sound.url
        global_sound = GlobalChatSettings.get_instance().default_sound
        return global_sound.url if global_sound else None


class Dialogue(models.Model):
    """Диалог между двумя пользователями."""
    participant1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dialogues_as_1"
    )
    participant2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dialogues_as_2"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

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
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Диалог: {self.participant1} ↔ {self.participant2}"

    def get_other_participant(self, user):
        """Возвращает собеседника для данного пользователя."""
        return self.participant2 if user == self.participant1 else self.participant1

    def get_unread_count(self, user):
        """Количество непрочитанных сообщений для пользователя."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def mark_as_read(self, user):
        """Отметить все сообщения как прочитанные для пользователя."""
        self.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

    def get_last_message(self):
        """Получить последнее сообщение диалога."""
        return self.messages.last()


class Message(models.Model):
    """Сообщение в диалоге."""
    dialogue = models.ForeignKey(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    text = models.TextField("Текст сообщения")
    is_read = models.BooleanField("Прочитано", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}"


class UserOnlineStatus(models.Model):
    """Статус онлайн пользователя."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="online_status"
    )
    last_seen = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False, db_index=True)

    # Время, через которое пользователь считается оффлайн (в минутах)
    OFFLINE_THRESHOLD = 5

    class Meta:
        verbose_name = "Статус онлайн"
        verbose_name_plural = "Статусы онлайн"

    def __str__(self):
        status = "🟢" if self.is_online else "⚪"
        return f"{status} {self.user}"

    def update_status(self):
        """Обновить статус на основе last_seen."""
        threshold = timezone.now() - timedelta(minutes=self.OFFLINE_THRESHOLD)
        was_online = self.is_online
        self.is_online = self.last_seen >= threshold
        if was_online != self.is_online:
            self.save(update_fields=["is_online"])
        return self.is_online

    def ping(self):
        """Обновить last_seen и статус."""
        self.last_seen = timezone.now()
        self.is_online = True
        self.save(update_fields=["last_seen", "is_online"])
        return self.is_online