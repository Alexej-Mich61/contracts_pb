#apps/audit/models.py
from django.conf import settings
from django.db import models


class Log(models.Model):
    """Одна строка = одно изменение поля договора."""

    contract = models.ForeignKey(
        "contract_core.Contract",
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Договор",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Пользователь",
    )
    field = models.CharField("Поле", max_length=50)
    old_value = models.TextField("Старое значение", blank=True)
    new_value = models.TextField("Новое значение", blank=True)
    timestamp = models.DateTimeField("Время", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись истории"
        verbose_name_plural = "История изменений"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["contract", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.contract} – {self.field} – {self.timestamp:%d.%m.%Y %H:%M}"