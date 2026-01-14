#apps/contract_works/models.py
from django.db import models


class Work(models.Model):
    # 5 типов работ (соответствуют типам договоров)
    TYPE_ONEOFF_LICENSEE = "oneoff_licensee"
    TYPE_LONGTERM_TO_LICENSEE = "longterm_to_licensee"
    TYPE_SMR_LICENSEE = "smr_licensee"
    TYPE_ONEOFF_LAB = "oneoff_lab"
    TYPE_LONGTERM_LAB = "longterm_lab"

    WORK_TYPE_CHOICES = (
        (TYPE_ONEOFF_LICENSEE, "Разовая работа (лицензиат)"),
        (TYPE_LONGTERM_TO_LICENSEE, "Периодическая работа ТО (лицензиат)"),
        (TYPE_SMR_LICENSEE, "Строительно-монтажная работа (лицензиат)"),
        (TYPE_ONEOFF_LAB, "Разовая работа (лаборатория)"),
        (TYPE_LONGTERM_LAB, "Периодическая работа (лаборатория)"),
    )

    # 3 вида компаний-исполнителей
    COMPANY_KIND_LICENSEE = "licensee"
    COMPANY_KIND_LAB = "lab"
    COMPANY_KIND_SUBCONTRACTOR = "subcontractor"

    COMPANY_KIND_CHOICES = (
        (COMPANY_KIND_LICENSEE, "Лицензиат"),
        (COMPANY_KIND_LAB, "Лаборатория"),
        (COMPANY_KIND_SUBCONTRACTOR, "Субподрядчик"),
    )

    name = models.CharField("Наименование работы", max_length=255)
    work_type = models.CharField(
        "Тип работы", max_length=25, choices=WORK_TYPE_CHOICES, db_index=True
    )
    company_kind = models.CharField(
        "Вид компании", max_length=15, choices=COMPANY_KIND_CHOICES, db_index=True,
        null=True,  # ← добавь
        blank=True,  # ←
    )

    class Meta:
        verbose_name = "Вид работы"
        verbose_name_plural = "Виды работ"
        ordering = ["name"]
        # уникальность пары «название + тип + вид компании»
        unique_together = ("name", "work_type", "company_kind")

    def __str__(self):
        return f"{self.get_work_type_display()} – {self.name}"