# apps/companies/models.py
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from apps.contract_core.validators import inn_validator




class Company(models.Model):
    """Справочник организаций: заказчик, лицензиат, лаборатория, субподрядчик."""
    # роли
    is_customer = models.BooleanField("Заказчик", default=True, db_index=True)
    is_licensee = models.BooleanField("Лицензиат МЧС", default=False, db_index=True)
    is_lab = models.BooleanField("Лаборатория", default=False, db_index=True)
    is_subcontractor = models.BooleanField("Субподрядчик", default=False, db_index=True)

    name = models.CharField("Название", max_length=255, db_index=True)
    inn = models.CharField(
        "ИНН",
        max_length=12,
        unique=True,          # ← уникальность
        validators=[inn_validator],
        help_text="10 цифр – юрлицо, 12 – физлицо",
    )
    fias_code = models.CharField(
        "Код ФИАС",
        max_length=50,
        blank=True,
        help_text="Код объекта по ФИАС (необязательно)",
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["name"]

        # составной индекс «роль + название» — ускоряет фильтры админки
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["inn"]),
            models.Index(fields=["is_customer", "name"]),
            models.Index(fields=["is_licensee", "name"]),
            models.Index(fields=["is_lab", "name"]),
            models.Index(fields=["is_subcontractor", "name"]),
        ]

    def __str__(self):
        return self.name


    def clean(self):
        # проверка «хотя бы одна роль» (уже было)
        if not any((self.is_customer, self.is_licensee, self.is_lab, self.is_subcontractor)):
            raise ValidationError("Необходимо выбрать хотя бы одну роль организации.")

        # дружелюбное сообщение при дубле ИНН
        if self.inn:  # заполнено
            qs = Company.objects.filter(inn=self.inn)
            if self.pk:  # редактирование – исключаем себя
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"inn": f"Компания с ИНН «{self.inn}» уже существует в базе. "
                            f"Проверьте справочник или обратитесь к администратору."}
                )



