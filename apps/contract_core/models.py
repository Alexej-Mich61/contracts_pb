# apps/contract_core/models.py
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.db import models
from django.utils import timezone
import datetime

from auditlog.registry import auditlog

from config.middleware import get_current_user
from .managers import ContractManager
from .validators import inn_validator, file_validator
from .services import ContractStatusCalculator
from .services.uuid_path_generator import (
    contract_file_path,
    act_file_path,
    final_act_file_path,
)



# ---------- НАСТРОЙКА ДЛЯ СТАТУСОВ КОНТРАКТОВ ----------
class ContractSettings(models.Model):
    """Единая строка на весь проект – настройки расчёта статусов контрактов."""
    days_before_expires = models.PositiveSmallIntegerField(
        "Дней до статуса «Истекает»",
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Если до конца срока ≤ этого числа – статус «Истекает»",
    )
    longterm_status_time = models.TimeField(
        "Время обновления долгосрочных",
        default=datetime.time(2, 0),  # 02:00
    )
    oneoff_status_time = models.TimeField(
        "Время обновления разовых",
        default=datetime.time(3, 0),  # 03:00
    )

    class Meta:
        verbose_name = "Настройки статусов договоров"
        verbose_name_plural = "Настройки статусов договоров"


    def __str__(self):
        return f"До «Истекает» {self.days_before_expires} дн., обновления в {self.longterm_status_time} и {self.oneoff_status_time}"

    @classmethod
    def get_settings(cls):
        """Получить единственную запись настроек (создаёт, если нет)."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


# ---------- СПРАВОЧНИКИ (регион/район) ----------
class Region(models.Model):
    name = models.CharField(
        "Наименование",
        max_length=100,
        unique=True,
        help_text="Например: Ростовская область"
    )
    fias_code = models.CharField(
        "Код ФИАС",
        max_length=50,
        blank=True,
        null=True,
        help_text="Код ФИАС (необязательно)"
    )
    region_code = models.CharField(
        "Код региона",
        max_length=50,
        blank=True,
        null=True,
        help_text="Код региона (необязательно)"
    )

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="districts")
    name = models.CharField(
        "Наименование",
        max_length=100,
        help_text="Укажите район (муниципальное образование). Например: Тарасовский район или город Азов"
    )
    fias_code = models.CharField(
        "Код ФИАС",
        max_length=50,
        blank=True,
        null=True,
        help_text="Код ФИАС (необязательно)"
    )
    district_code = models.CharField(
        "Код района",
        max_length=50,
        blank=True,
        null=True,
        help_text="Код района (необязательно)"
    )

    class Meta:
        verbose_name = "Район"
        verbose_name_plural = "Районы"
        ordering = ["name"]
        unique_together = ("region", "name")

    def __str__(self):
        return f"{self.region} – {self.name}"


# ---------- РАБОТЫ ----------
class Work(models.Model):
    """Справочник видов работ (3 типа)."""
    class WorkType(models.TextChoices):
        ONEOFF_LICENSEE = "work_oneoff_licensee", "Разовая работа (лицензиат)"
        LONGTERM_TO_LICENSEE = "work_longterm_to_licensee", "Периодическая работа ТО (лицензиат)"
        ONEOFF_LAB = "work_oneoff_lab", "Разовая работа (лаборатория)"

    name = models.CharField(
        "Наименование работы",
        max_length=255,
        db_index=True,
        help_text="Например: Монтаж СПС"
    )
    is_active = models.BooleanField("Активна", default=True)
    work_type = models.CharField("Тип работы", max_length=25, choices=WorkType.choices, db_index=True)
    description = models.TextField("Описание", blank=True, max_length=500)

    class Meta:
        verbose_name = "Вид работы"
        verbose_name_plural = "Виды работ"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=['name', 'work_type'], name='work_name_type_unique'),
        ]

    def __str__(self):
        return f"{self.get_work_type_display()} – {self.name}"


# ---------- КОМПАНИИ ----------
class Company(models.Model):
    """Справочник организаций: заказчик, лицензиат, лаборатория, субподрядчик."""
    is_customer = models.BooleanField("Заказчик", default=True, db_index=True)
    is_licensee = models.BooleanField("Лицензиат МЧС", default=False, db_index=True)
    is_laboratory = models.BooleanField("Лаборатория", default=False, db_index=True)
    is_subcontractor = models.BooleanField("Субподрядчик", default=False, db_index=True)


    notification_agreed = models.BooleanField(
        "Согласие на уведомление",
        default=False,
        db_index=True,
        help_text="Компания дала согласие на получение уведомлений"
    )

    name = models.CharField(
        "Название",
        max_length=255,
        help_text="Укажите краткое название, например: ООО Ромашка или МБДОУ Д/с № 1",
        db_index=True)
    inn = models.CharField(
        "ИНН",
        max_length=12,
        unique=True,
        validators=[inn_validator],
        help_text="10 цифр – юрлицо, 12 – физлицо",
    )
    email = models.EmailField(
        "E-mail компании",
        blank=True,
        null=True,
        help_text="E-mail компании (необязательно)",
    )

    phone = models.CharField(
        "Телефон компании",
        max_length=20,
        blank=True,
        default="",
        help_text="Телефон компании (необязательно)",
    )

    fias_code = models.CharField(
        "Код ФИАС",
        max_length=50,
        blank=True,
        null=True,
        help_text="Код объекта по ФИАС (необязательно)",
    )

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["inn"]),
            models.Index(fields=["is_customer", "name"]),
            models.Index(fields=["is_licensee", "name"]),
            models.Index(fields=["is_laboratory", "name"]),
            models.Index(fields=["is_subcontractor", "name"]),
            models.Index(fields=["notification_agreed"]),
            models.Index(fields=["email"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                name='unique_company_email',
                condition=models.Q(email__isnull=False) & ~models.Q(email='')
            ),
        ]


    def __str__(self):
        return self.name or f"Компания {self.pk}"

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        if self.inn:
            qs = Company.objects.filter(inn=self.inn)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'inn': f"Компания с ИНН «{self.inn}» уже существует в базе."
                })

    def clean(self):
        if not any([self.is_customer, self.is_licensee, self.is_laboratory, self.is_subcontractor]):
            raise ValidationError("Необходимо выбрать хотя бы одну роль организации.")


# ---------- СПРАВОЧНИК СТАДИЙ ПОДПИСАНИЯ ----------
class SigningStage(models.Model):
    """Справочник стадий подписания договора."""
    name = models.CharField(
        "Название стадии",
        max_length=50,
        unique=True,
        help_text="Например: Подписан или Расторжение"
    )
    slug = models.SlugField("Слаг стадии", max_length=50, unique=True)
    order = models.PositiveSmallIntegerField(
        "Порядок отображения",
        default=1,  # ← начинаем с 1
        help_text="Чем меньше число, тем выше в списке. Начинайте с 1."
    )
    is_final = models.BooleanField(
        "Финальная стадия",
        default=False
    )
    description = models.TextField("Описание", blank=True, max_length=500)

    class Meta:
        verbose_name = "Стадия подписания"
        verbose_name_plural = "Стадии подписания"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


# ---------- ТЕКУЩАЯ СТАДИЯ ПОДПИСАНИЯ ДОГОВОРА ----------
class ContractSigningStage(models.Model):
    """Текущая стадия подписания конкретного договора (одна на договор)."""
    contract = models.OneToOneField(
        'Contract',
        on_delete=models.CASCADE,
        related_name='signing_stage',
        verbose_name="Договор"
    )
    stage = models.ForeignKey(
        SigningStage,
        on_delete=models.PROTECT,
        verbose_name="Текущая стадия"
    )
    changed_at = models.DateTimeField("Дата изменения", auto_now=True)
    changed_by = models.ForeignKey(
        'identity.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто изменил",
        related_name="changed_signing_stages",
        editable=False,
    )
    note = models.TextField("Примечание", blank=True, max_length=200)

    def save(self, *args, **kwargs):
        current_user = get_current_user()
        if current_user and not self.pk:
            self.changed_by = current_user
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Стадия подписания договора"
        verbose_name_plural = "Стадии подписания договоров"
        ordering = ["changed_at"]
        permissions = [
            ("can_edit_signing_stages", "Может редактировать стадии подписания"),
        ]

    def __str__(self):
        try:
            return f"{self.contract} — {self.stage}"
        except:
            return f"Стадия для договора {self.contract_id}"


# ---------- СПРАВОЧНИК СИСТЕМ ----------
class SystemType(models.Model):
    """Справочник систем, которые нужно проверять/отмечать."""
    name = models.CharField(
        "Название системы",
        max_length=100,
        unique=True,
        help_text="Например: Сполох"
    )

    slug = models.SlugField("Слаг системы", max_length=50, unique=True)
    description = models.TextField("Описание", blank=True, max_length=500)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Тип системы"
        verbose_name_plural = "Типы систем"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------- ОТМЕТКИ ПО СИСТЕМАМ ----------
class ContractSystemCheck(models.Model):
    """Отметка проверки/действия по конкретной системе для договора."""
    contract = models.ForeignKey(
        'Contract',
        on_delete=models.CASCADE,
        related_name='system_checks',
        verbose_name="Договор"
    )
    system_type = models.ForeignKey(
        SystemType,
        on_delete=models.PROTECT,
        verbose_name="Система"
    )
    last_checked = models.DateField(
        verbose_name="Дата последней отметки",
        null=True,
        blank=True,
    )
    checked_by = models.ForeignKey(
        'identity.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто отметил",
        related_name="system_checks",
        editable=False,
    )
    note = models.CharField("Примечание", max_length=200, blank=True)

    def save(self, *args, **kwargs):
        current_user = get_current_user()
        if current_user and not self.pk:
            self.checked_by = current_user
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Проверка системы"
        verbose_name_plural = "Проверки систем"
        unique_together = ('contract', 'system_type')
        ordering = ['system_type__name']
        permissions = [
            ("can_edit_system_checklist", "Может редактировать чек-лист систем"),
        ]
        indexes = [
            models.Index(fields=['last_checked']),
        ]

    def __str__(self):
        date_str = self.last_checked.strftime("%d.%m.%Y") if self.last_checked else "не отмечено"
        try:
            return f"{self.contract} — {self.system_type} ({date_str})"
        except:
            return f"Проверка системы для договора {self.contract_id}"


# ---------- КОНТРАКТ (ОСНОВНАЯ МОДЕЛЬ) ----------
class Contract(models.Model):
    class Type(models.TextChoices):
        ONEOFF_LICENSEE = "oneoff_licensee", "Разовый (лицензиат)"
        LONGTERM_TO_LICENSEE = "longterm_to_licensee", "Долгосрочный ТО (лицензиат)"
        ONEOFF_LAB = "oneoff_lab", "Разовый (лаборатория)"

    # Служебные флаги
    is_trash = models.BooleanField("В корзине", default=False, db_index=True)
    is_archived = models.BooleanField("В архиве", default=False, db_index=True)

    # Основные сведения
    type = models.CharField("Тип договора", max_length=25, choices=Type.choices, db_index=True)
    number = models.CharField("Номер договора", max_length=50, blank=True, null=True)
    date_concluded = models.DateField("Дата заключения", blank=True, null=True)

    customer = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        limit_choices_to={"is_customer": True},
        related_name="contracts_customer",
        verbose_name="Заказчик",
    )
    date_start = models.DateField("Начало действия")
    date_end = models.DateField("Окончание действия")

    executor = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        limit_choices_to=Q(is_licensee=True) | Q(is_laboratory=True),
        verbose_name="Исполнитель",
        related_name="contracts_executor",
    )

    work = models.ForeignKey(
        Work,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="Вид работы",
    )

    note = models.TextField("Примечание", blank=True, null=True)

    # Файлы
    file = models.FileField(
        "Файл договора",
        upload_to=contract_file_path,  # <-- Было: "contracts/%Y/%m/%d"
        blank=True,
        validators=[file_validator],
        help_text="Любой формат, кроме .exe и пр. До 100 МБ",
    )

    # Финансы
    total_sum = models.DecimalField(
        "Сумма контракта общая",
        max_digits=12,
        decimal_places=2,
        default=0.00)
    monthly_sum = models.DecimalField(
        "Сумма контракта в месяц",
        max_digits=12,
        decimal_places=2,
        default=0.00)
    advance = models.DecimalField("Аванс", max_digits=12, decimal_places=2, default=0.00)

    # Статус
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_ACTIVE_EXPIRES = "active_expires"
    STATUS_ACTIVE_EXPIRED = "active_expired"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Ожидание"),
        (STATUS_ACTIVE, "Действует"),
        (STATUS_ACTIVE_EXPIRES, "Истекает"),
        (STATUS_ACTIVE_EXPIRED, "Истёк"),
        (STATUS_COMPLETED, "Завершён"),
    )
    status = models.CharField(
        "Статус",
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )

    # Служебные
    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    creator = models.ForeignKey(
        'identity.User',
        on_delete=models.PROTECT,
        verbose_name="Автор",
        related_name="contracts_created",
        null=True,
        blank=True,
        editable=False,
    )
    updater = models.ForeignKey(
        'identity.User',
        on_delete=models.PROTECT,
        verbose_name="Обновил",
        related_name="contracts_updated",
        null=True,
        blank=True,
        editable=False,
    )

    objects = ContractManager()

    class Meta:
        verbose_name = "Договор"
        verbose_name_plural = "Договоры"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["executor", "status"]),
            models.Index(fields=["is_trash"]),
            models.Index(fields=["is_archived"]),
        ]

    def save(self, *args, **kwargs):
        current_user = get_current_user()
        if current_user:
            if not self.pk:  # создание
                self.creator = current_user
            self.updater = current_user  # всегда обновляем

        # Пересчёт статуса
        new_status = ContractStatusCalculator.calculate_status(self)
        if new_status != self.status:
            self.status = new_status

        super().save(*args, **kwargs)

    def __str__(self):
        try:
            return f"{self.number or 'б/н'} ({self.get_type_display()})"
        except:
            return f"Договор {self.pk}"


# ---------- ИТОГОВЫЙ АКТ ----------
class FinalAct(models.Model):
    """Итоговый акт по договору (один на договор)."""
    contract = models.OneToOneField(
        'Contract',
        on_delete=models.CASCADE,
        related_name='final_act',
        verbose_name="Договор"
    )
    present = models.BooleanField("Акт сформирован", default=False)
    date = models.DateField("Дата итогового акта", blank=True, null=True)
    file = models.FileField(
        "Файл акта",
        upload_to=final_act_file_path,  # <-- Было: "acts_final/%Y/%m/%d"
        blank=True,
        null=True,
        validators=[file_validator],
        help_text="Любой формат, кроме .exe и пр. До 100 МБ",
    )
    checked_by = models.ForeignKey(
        'identity.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто отметил",
        related_name="final_acts_checked",
        editable=False,
    )
    checked_at = models.DateTimeField("Дата отметки", auto_now_add=True, blank=True)
    note = models.TextField(
        "Примечание к акту",
        blank=True,
        max_length=200,
        help_text="Примечание (необязательно)"
    )

    class Meta:
        verbose_name = "Итоговый акт"
        verbose_name_plural = "Итоговые акты"
        permissions = [
            ("can_mark_final_act", "Может отмечать итоговый акт сформированным"),
        ]

    def __str__(self):
        status = "сформирован" if self.present else "не сформирован"
        try:
            return f"Акт по {self.contract} — {status}"
        except:
            return f"Акт {self.pk}"

    def mark_as_present(self, user: 'identity.User') -> None:
        if not user or not user.is_authenticated:
            raise ValueError("Нельзя отметить акт без пользователя")
        self.present = True
        self.checked_by = user
        self.checked_at = timezone.now()
        self.save(update_fields=['present', 'checked_by', 'checked_at'])


# ---------- ПРОМЕЖУТОЧНЫЙ АКТ ----------
class InterimAct(models.Model):
    """Промежуточный этапный акт (много штук к одному договору)."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="interim_acts")
    title = models.CharField("Название", max_length=50, default="Этап Акт")
    date = models.DateField("Дата")
    file = models.FileField(
        "Файл акта",
        upload_to=act_file_path,  # <-- Было: "acts/%Y/%m/%d"
        blank=True,
        validators=[file_validator],
        help_text="Любой формат, кроме .exe и пр. До 100 МБ",
    )

    class Meta:
        verbose_name = "Промежуточный акт"
        verbose_name_plural = "Промежуточные акты"
        ordering = ["date"]
        permissions = [
            ("can_edit_interim_act", "Может редактировать промежуточные акты"),
        ]

    def __str__(self):
        try:
            return f"{self.title} от {self.date} (договор {self.contract.number or self.contract.pk})"
        except:
            return f"Промежуточный акт {self.pk}"


# ---------- ОБЪЕКТЫ ЗАЩИТЫ ----------
class ProtectionObject(models.Model):
    """Объект защиты (много штук к одному договору)."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="contract_objects") # было - objects
    name = models.CharField(
        "Наименование объекта защиты",
        max_length=255,
        help_text = "Назовите объект (здание или помещение), ориентируясь на спецификацию договора, "
                    "например: Гараж МБУЗ ЦРБ или Главный корпус МБДОУ ДС №1"
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        verbose_name="Район",
        related_name="protection_objects",
        null=True,
        blank=True
    )
    address = models.TextField(
        "Адрес",
        max_length=700,
        help_text="Укажите почтовый адрес"
    )
    contacts = models.TextField(
        "Контакты",
        blank=True,
        null=True,
        help_text="Укажите контакты (необязательно)"
    )

    subcontractor = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        limit_choices_to={"is_subcontractor": True},
        verbose_name="Субподрядчик",
        blank=True,
        null=True,
        related_name="protection_objects_sub",
    )

    total_sum_subcontract = models.DecimalField(
        "Сумма субконтракта общая",
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    monthly_sum_subcontract = models.DecimalField(
        "Сумма субконтракта в месяц",
        max_digits=12,
        decimal_places=2,
        default=0.00
    )

    @property
    def region(self):
        return self.district.region if self.district else None

    class Meta:
        verbose_name = "Объект защиты"
        verbose_name_plural = "Объекты защиты"
        ordering = ["name"]

    def __str__(self):
        loc = f" ({self.region} – {self.district})" if self.district else ""
        return f"{self.name}{loc}"


# ---------- АБОНЕНТСКИЕ КОМПЛЕКТЫ ----------
class Ak(models.Model):
    """Абонентский комплект (много-ко-многим к объектам защиты)."""
    protection_objects = models.ManyToManyField(
        ProtectionObject,
        related_name="aks",
        verbose_name="Объекты защиты",
        blank=True,
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        verbose_name="Район установки",
        blank=True,
        null=True,
    )
    number = models.PositiveIntegerField(
        "Номер АК",
        validators=[MinValueValidator(1), MaxValueValidator(99999999)],
        help_text="Макс. 8 цифр. Номер из базы ОКО, например 6001",
    )
    name = models.CharField(
        "Наименование",
        max_length=255,
        help_text="Укажите название АК (см. базу ОКО)"
    )
    address = models.TextField(
        "Адрес установки",
        max_length=700,
        help_text="Укажите адрес АК (см. базу ОКО)"
    )

    @property
    def region(self):
        return self.district.region if self.district else None

    class Meta:
        verbose_name = "Абонентский комплект (АК)"
        verbose_name_plural = "Абонентские комплекты (АК)"
        unique_together = ("number", "district")
        ordering = ["number"]
        indexes = [
            models.Index(fields=["number"], name="ak_number_idx"),
            models.Index(fields=["district"], name="ak_district_idx"),
        ]

    def __str__(self):
        return f"АК №{self.number} – {self.name}"

# auditlog
auditlog.register(Contract)
auditlog.register(FinalAct)
auditlog.register(InterimAct)
auditlog.register(ContractSigningStage)
auditlog.register(ContractSystemCheck)
auditlog.register(ProtectionObject)
auditlog.register(Ak)
auditlog.register(Company)

