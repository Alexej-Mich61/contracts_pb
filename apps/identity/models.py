# apps/identity/models.py
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.contract_core.models import Company


class UserCategory:
    """Константы категорий пользователей."""
    ADMIN = "admin"
    MANAGER = "manager"
    GUEST = "guest"
    CHOICES = (
        (ADMIN, _("Администратор")),
        (MANAGER, _("Менеджер")),
        (GUEST, _("Гость")),
    )


class ManagerPermission(models.Model):
    """
    Разрешения для менеджеров.
    One-to-One с User, создается автоматически при назначении категории MANAGER.
    """
    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="manager_permissions",
        verbose_name=_("пользователь"),
    )

    # === Права менеджеров для договоров ===
    can_add_contract = models.BooleanField(
        _("может добавлять договоры"),
        default=True,
        help_text=_("Разрешение на создание новых договоров"),
    )

    can_edit_contract_main_fields = models.BooleanField(
        _("может редактировать основные поля договора"),
        default=False,
        help_text=_("Редактирование основных данных договора (номер, даты, суммы, вид работы и т.д.)"),
    )

    can_edit_signing_stages = models.BooleanField(
        _("может редактировать стадии подписания"),
        default=False,
    )

    can_edit_system_checklist = models.BooleanField(
        _("может редактировать чек-лист Системы"),
        default=False,
    )

    can_mark_final_act = models.BooleanField(
        _("может отмечать итоговый акт сформированным"),
        default=False,
    )

    can_edit_interim_act = models.BooleanField(
        _("может редактировать этапные акты"),
        default=False,
    )

    # === Права менеджеров для компаний ===
    can_manage_companies = models.BooleanField(
        _("может управлять компаниями"),
        default=True,
        help_text=_("Добавление и редактирование организаций (компаний)"),
    )

    # === Права менеджеров для АК (абонентских комплектов) ===
    can_manage_aks = models.BooleanField(
        _("может управлять абонентскими комплектами (АК)"),
        default=True,
        help_text=_("Добавление и редактирование АК (абонентских комплектов)"),
    )

    updated_at = models.DateTimeField(_("обновлено"), auto_now=True)

    class Meta:
        verbose_name = _("разрешения менеджера")
        verbose_name_plural = _("разрешения менеджеров")

        # Индексы для всех часто проверяемых прав
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["can_add_contract"]),
            models.Index(fields=["can_edit_contract_main_fields"]),
            models.Index(fields=["can_edit_signing_stages"]),
            models.Index(fields=["can_edit_system_checklist"]),
            models.Index(fields=["can_mark_final_act"]),
            models.Index(fields=["can_edit_interim_act"]),
            models.Index(fields=["can_manage_companies"]),
            models.Index(fields=["can_manage_aks"]),
        ]

    def __str__(self):
        return f"Права менеджера: {self.user.get_full_name() or self.user.username}"


class User(AbstractUser):
    """Пользователь системы."""
    email = models.EmailField(_("email"), unique=True)
    phone = models.CharField(_("телефон"), max_length=20, blank=True)
    avatar = models.ImageField(
        _("аватар"),
        upload_to="avatars/%Y/%m/%d",
        blank=True,
        default="default_img.png",
    )
    news_is_active = models.BooleanField(
        _("рассылка активна"),
        default=True,
        db_index=True
    )
    category = models.CharField(
        _("категория"),
        max_length=20,
        choices=UserCategory.CHOICES,
        default=UserCategory.GUEST,
        db_index=True,
    )
    is_system = models.BooleanField(
        _("системный пользователь"),
        default=False,
        editable=False,
        help_text=_("Пользователь от имени системы"),
    )

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username

    def clean(self):
        """Валидация системного пользователя."""
        if self.is_system:
            if self.is_staff or self.is_superuser:
                raise ValidationError(
                    _("Системный пользователь не может быть staff или superuser")
                )
            if self.category != UserCategory.GUEST:
                raise ValidationError(
                    _("Системный пользователь должен иметь категорию GUEST")
                )

    def save(self, *args, **kwargs):
        if self.is_system:
            self.is_staff = False
            self.is_superuser = False
            self.category = UserCategory.GUEST

        super().save(*args, **kwargs)
        self._sync_groups()
        self._sync_manager_permissions()

    def _sync_groups(self):
        """Синхронизирует группы Django с категорией пользователя."""
        group_map = {
            UserCategory.ADMIN: "Admins",
            UserCategory.MANAGER: "Managers",
            UserCategory.GUEST: "Guests",
        }
        category_groups = list(group_map.values())
        self.groups.remove(*self.groups.filter(name__in=category_groups))

        if self.category in group_map:
            group, _ = Group.objects.get_or_create(name=group_map[self.category])
            self.groups.add(group)

    def _sync_manager_permissions(self):
        """Создает или удаляет ManagerPermission в зависимости от категории."""
        has_perms = hasattr(self, "manager_permissions")
        if self.category == UserCategory.MANAGER and not has_perms:
            ManagerPermission.objects.create(user=self)
        elif self.category != UserCategory.MANAGER and has_perms:
            self.manager_permissions.delete()

    @property
    def is_admin(self) -> bool:
        return self.category == UserCategory.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.category == UserCategory.MANAGER

    @property
    def is_guest(self) -> bool:
        return self.category == UserCategory.GUEST

    # ====================== МЕТОДЫ ПРОВЕРКИ РАЗРЕШЕНИЙ ======================

    def has_manager_perm(self, perm_name: str) -> bool:
        """Вспомогательный метод — безопасно получает флаг из ManagerPermission"""
        if not self.is_manager or not hasattr(self, 'manager_permissions'):
            return False
        return getattr(self.manager_permissions, perm_name, False)

    # === Глобальные права (для кнопок "Добавить", "Редактировать" и т.д.) ===

    def can_add_contract(self) -> bool:
        """Может создавать новые договоры"""
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_add_contract')
        return False

    def can_edit_contract_main_fields(self) -> bool:
        """Может редактировать основные поля договора"""
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_edit_contract_main_fields')
        return False

    def can_manage_companies(self) -> bool:
        """Может добавлять и редактировать компании"""
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_manage_companies')
        return False

    def can_manage_aks(self) -> bool:
        """Может добавлять и редактировать АК"""
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_manage_aks')
        return False

    # === Гранулярные права внутри договоров ===

    def can_edit_signing_stages(self) -> bool:
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_edit_signing_stages')
        return False

    def can_edit_system_checklist(self) -> bool:
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_edit_system_checklist')
        return False

    def can_mark_final_act(self) -> bool:
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_mark_final_act')
        return False

    def can_edit_interim_act(self) -> bool:
        if self.is_superuser or self.is_admin:
            return True
        if self.is_manager:
            return self.has_manager_perm('can_edit_interim_act')
        return False

    # Устаревший метод оставляем для совместимости
    def get_manager_perm(self, attr: str) -> bool:
        """Безопасное получение прав менеджера (для обратной совместимости)."""
        if not self.is_manager:
            return False
        return getattr(self.manager_permissions, attr, False)


class Employee(models.Model):
    """
    Связь пользователя с компанией.
    ForeignKey - один пользователь может быть сотрудником нескольких компаний.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="employments",
        verbose_name=_("пользователь"),
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="employees",
        verbose_name=_("компания"),
    )
    is_active = models.BooleanField(_("активен"), default=True)
    created_at = models.DateTimeField(_("создан"), auto_now_add=True)

    class Meta:
        verbose_name = _("сотрудник компании")
        verbose_name_plural = _("сотрудники компании")
        ordering = ["-created_at"]
        # Запрещаем дублирование связи пользователь-компания
        unique_together = ("user", "company")

    def __str__(self):
        status = _("активен") if self.is_active else _("не активен")
        return f"{self.user} – {self.company} ({status})"