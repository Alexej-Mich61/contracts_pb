#apps/contract_works/models.py
from django.db import models
from apps.contract_core.models import Contract


class Work(models.Model):
    """Справочник видов работ (3 типа)."""
    WORK_TYPE_ONEOFF_LICENSEE = "work_oneoff_licensee"
    WORK_TYPE_LONGTERM_TO_LICENSEE = "work_longterm_to_licensee"
    WORK_TYPE_ONEOFF_LAB = "work_oneoff_lab"

    WORK_TYPE_CHOICES = (
        (WORK_TYPE_ONEOFF_LICENSEE, "Разовая работа (лицензиат)"),
        (WORK_TYPE_LONGTERM_TO_LICENSEE, "Периодическая работа ТО (лицензиат)"),
        (WORK_TYPE_ONEOFF_LAB, "Разовая работа (лаборатория)"),
    )

    name = models.CharField("Наименование работы", max_length=255, db_index=True)
    work_type = models.CharField("Тип работы", max_length=25, choices=WORK_TYPE_CHOICES, db_index=True)

    class Meta:
        verbose_name = "Вид работы"
        verbose_name_plural = "Виды работ"
        ordering = ["name"]
        # уникальность только по паре «название + тип»
        unique_together = ("name", "work_type")

    def __str__(self):
        return f"{self.get_work_type_display()} – {self.name}"


# Промежуточная M2M-модель (чтобы при удалении ни Contract, ни Work не исчезали)
class ContractWork(models.Model):
    """Связь Контракт ↔ Работа (многие-ко-многим)."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="contract_works")
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="contract_works")

    class Meta:
        verbose_name = "Работа договора"
        verbose_name_plural = "Работы договоров"
        unique_together = ("contract", "work")   # не дублировать