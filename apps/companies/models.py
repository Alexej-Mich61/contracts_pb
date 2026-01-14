# apps/companies/models.py
from django.contrib.auth import get_user_model
from django.db import models
from apps.contract_core.validators import inn_validator

User = get_user_model()


class Company(models.Model):
    """Справочник организаций (лицензиаты, лаборатории, субподрядчики)."""
    KIND_LICENSEE = "licensee"
    KIND_LAB = "lab"
    KIND_SUBCONTRACTOR = "subcontractor"

    KIND_CHOICES = (
        (KIND_LICENSEE, "Лицензиат МЧС"),
        (KIND_LAB, "Лаборатория"),
        (KIND_SUBCONTRACTOR, "Субподрядчик"),
    )

    name = models.CharField("Название", max_length=255)
    kind = models.CharField("Тип организации", max_length=15, choices=KIND_CHOICES, db_index=True)
    inn = models.CharField(
        "ИНН",
        max_length=12,
        blank=True,
        validators=[inn_validator],
        help_text="10 цифр – юрлицо, 12 – физлицо",
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    """Связь Пользователь ↔ Компания + роль + пермиссии для менеджера."""
    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        EMPLOYEE = "employee", "Сотрудник"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employees")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    role = models.CharField("Роль", max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField("Активен", default=True)

    # пермиссии для менеджера (для админа всё равно всё разрешено)
    can_delete_contract = models.BooleanField("Может удалять договоры", default=False)
    can_edit_systems = models.BooleanField("Может редактировать чек-лист Системы", default=False)
    can_edit_sign_stage = models.BooleanField(
        "Может редактировать чек-лист Стадии подписания", default=False
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "company")
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.user} – {self.company} ({self.get_role_display()})"

    # быстрые проверки
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    def is_employee(self) -> bool:
        return self.role == self.Role.EMPLOYEE


# ---------- методы Company после определения Employee ----------
def _add_employee(self, user, role="employee"):
    # импорт внутри, чтобы избежать циклического импорта при будущих изменениях
    from apps.companies.models import Employee
    Employee.objects.get_or_create(user=user, company=self, defaults={"role": role})


def _remove_employee(self, user):
    from apps.companies.models import Employee
    Employee.objects.filter(user=user, company=self).delete()


def _staff(self):
    return User.objects.filter(employees__company=self, employees__is_active=True)

# прицепляем методы к классу
Company.add_employee = _add_employee
Company.remove_employee = _remove_employee
Company.staff = property(_staff)
