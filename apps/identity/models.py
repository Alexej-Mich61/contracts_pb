#apps/identity/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.companies.models import Company



class User(AbstractUser):
    # 3 категории аккаунта
    class Category(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        GUEST = "guest", "Гость (только просмотр)"

    email = models.EmailField("email", unique=True)
    phone = models.CharField("телефон", max_length=20, blank=True)
    is_system = models.BooleanField("Системный пользователь", default=False, editable=False)

    # категория пользователя
    category = models.CharField(
        "Категория",
        max_length=10,
        choices=Category.choices,
        default=Category.GUEST,
        db_index=True,
    )

    # аватарка
    avatar = models.ImageField(
        "Аватар",
        upload_to="avatars/%Y/%m/",
        blank=True,
        default="default_img.png",  # положите файл в MEDIA_ROOT/default_img.png
    )

    # пермиссии (на уровне User – чтобы не создавать Employee для гостя)
    can_view_systems = models.BooleanField("Может видеть чек-лист Системы", default=False)
    can_edit_systems = models.BooleanField("Может редактировать чек-лист Системы", default=False)
    can_edit_sign_stage = models.BooleanField("Может редактировать чек-лист Стадии подписания", default=False)
    can_delete_contract = models.BooleanField("Может удалять договоры", default=False)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.get_full_name() or self.username

    # быстрые проверки
    def is_admin(self) -> bool:
        return self.category == self.Category.ADMIN

    def is_manager(self) -> bool:
        return self.category == self.Category.MANAGER

    def is_guest(self) -> bool:
        return self.category == self.Category.GUEST

    def has_full_access(self) -> bool:
        """Полный доступ – только у админа."""
        return self.is_admin or self.is_superuser


# Employee остаётся как связь «пользователь ↔ компания»
class Employee(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        EMPLOYEE = "employee", "Сотрудник"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employees")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    role = models.CharField("Роль в компании", max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField("Активен", default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "company")
        verbose_name = "Сотрудник компании"
        verbose_name_plural = "Сотрудники компании"

    def __str__(self):
        return f"{self.user} – {self.company} ({self.get_role_display()})"

    # быстрые проверки ролей
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    def is_employee(self) -> bool:
        return self.role == self.Role.EMPLOYEE

    # делегирование пермиссий от User
    @property
    def can_delete_contract(self):
        return self.user.can_delete_contract

    @property
    def can_edit_systems(self):
        return self.user.can_edit_systems

    @property
    def can_edit_sign_stage(self):
        return self.user.can_edit_sign_stage
