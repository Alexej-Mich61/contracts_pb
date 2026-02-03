# apps/mailing/models.py
from django.db import models
from apps.contract_core.models import Company


class Recipient(models.Model):
    """Адресат рассылки (заполняется админом)."""
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100)
    email = models.EmailField("E-mail", unique=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    position = models.CharField("Должность", max_length=120, blank=True)
    companies = models.ManyToManyField(
        Company,
        related_name="recipients",
        blank=True,
        verbose_name="Организации",
        help_text="Если не выбрано — письмо уйдёт всем, у кого активна рассылка.",
    )
    news_is_active = models.BooleanField("Рассылка активна", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Получатель рассылки"
        verbose_name_plural = "Получатели рассылки"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name} {self.first_name} <{self.email}>"