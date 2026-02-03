# apps/identity/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.contract_core.models import Company


class User(AbstractUser):
    """Пользователь системы с категорией и дополнительными разрешениями."""
    class Category(models.TextChoices):
        ADMIN = "admin", _("Администратор")
        MANAGER = "manager", _("Менеджер")
        BOOKKEEPER = "bookkeeper", _("Бухгалтер")
        SYSTEM_MANAGER = "system_manager", _("Диспетчер")
        GUEST = "guest", _("Гость")

    email = models.EmailField(_("email"), unique=True)
    phone = models.CharField(_("телефон"), max_length=20, blank=True)
    category = models.CharField(
        _("категория"),
        max_length=20,
        choices=Category.choices,
        default=Category.GUEST,
        db_index=True,
    )
    avatar = models.ImageField(
        _("аватар"),
        upload_to="avatars/%Y/%m/%d",
        blank=True,
        default="default_img.png",
    )
    news_is_active = models.BooleanField("Рассылка активна", default=True, db_index=True)

    # Вариативные права только для MANAGER
    can_mark_final_act = models.BooleanField(
        _("может отмечать итоговый акт сформированным"),
        default=False,
        help_text=_("Только для категории MANAGER"),
    )
    can_edit_system_checklist = models.BooleanField(
        _("может редактировать чек-лист Системы"),
        default=False,
        help_text=_("Только для категории MANAGER"),
    )
    can_edit_signing_stages = models.BooleanField(
        _("может редактировать стадии подписания"),
        default=False,
        help_text=_("Только для категории MANAGER"),
    )
    can_edit_interim_act = models.BooleanField(
        _("может редактировать этапные акты"),
        default=False,
        help_text=_("Только для категории MANAGER"),
    )

    is_system = models.BooleanField(
        "Системный пользователь",
        default=False,
        editable=False,
        help_text="Пользователь от имени системы (уведомления, чат-боты и т.д.)",
    )

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        if self.is_system:
            self.is_staff = False  # системный пользователь не должен иметь доступ в админку
            self.is_superuser = False
            self.set_unusable_password()  # запрещаем логин паролем
        super().save(*args, **kwargs)


class Employee(models.Model):
    """Связь пользователя с компанией (сотрудник компании)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employees")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    is_active = models.BooleanField(_("активен"), default=True)
    created_at = models.DateTimeField(_("создан"), auto_now_add=True)

    class Meta:
        unique_together = ("user", "company")
        verbose_name = _("сотрудник компании")
        verbose_name_plural = _("сотрудники компании")

    def __str__(self):
        return f"{self.user} – {self.company} ({'активен' if self.is_active else 'не активен'})"