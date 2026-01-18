# apps/audit/models.py
from django.conf import settings
from django.db import models

class Event(models.Model):
    """Конкретное событие договора: создан, статус изменён, удалён в корзину и т.д."""
    EVENT_CREATED = "created"
    EVENT_UPDATED = "updated"
    EVENT_TRASHED = "trashed"
    EVENT_RESTORED = "restored"
    EVENT_STATUS_CHANGED = "status_changed"
    EVENT_DATE_CHANGED = "date_changed"

    EVENT_CHOICES = (
        (EVENT_CREATED, "Создан"),
        (EVENT_UPDATED, "Обновлён"),
        (EVENT_TRASHED, "Удалён в корзину"),
        (EVENT_RESTORED, "Восстановлен из корзины"),
        (EVENT_STATUS_CHANGED, "Изменён статус"),
        (EVENT_DATE_CHANGED, "Изменены сроки"),
    )

    contract = models.ForeignKey(
        "contract_core.Contract",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Договор",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь",
    )
    event_type = models.CharField("Событие", max_length=20, choices=EVENT_CHOICES)
    old_value = models.CharField("Старое значение", max_length=100, blank=True)
    new_value = models.CharField("Новое значение", max_length=100, blank=True)
    created_at = models.DateTimeField("Время", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Событие договора"
        verbose_name_plural = "События договоров"
        ordering = ["-created_at"]

    def __str__(self):
        # готовая строка для лога / чата / письма
        user = self.user.get_full_name() or self.user.username if self.user else "Система"
        contract = self.contract.number or f"б/н ({self.contract.pk})"
        event_text = self.get_event_type_display()

        if self.old_value and self.new_value:
            event_text += f": {self.old_value} → {self.new_value}"

        return f"{self.created_at:%d.%m.%Y %H:%M}  {user}  договор {contract}  {event_text}"