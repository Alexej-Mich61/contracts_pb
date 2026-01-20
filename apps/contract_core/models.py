# apps/contract_core/models.py
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator

from .managers import ContractManager
from .validators import inn_validator, file_validator
from django.db import models
from apps.companies.models import Company
from django.utils import timezone
import datetime

User = get_user_model()

# ---------- СПРАВОЧНИКИ (регион/район) ----------


class ContractSettings(models.Model):
    """Единая строка на весь проект – настройки расчёта статусов."""
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


# Утилита – получение настроек
def get_contract_settings():
    return ContractSettings.objects.first() or ContractSettings.objects.create()



class Region(models.Model):
    name = models.CharField("Наименование", max_length=100, unique=True)
    fias_code = models.CharField("Код ФИАС", max_length=50, blank=True, null=True)
    region_code = models.CharField("Код региона", max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="districts")
    name = models.CharField("Наименование", max_length=100)
    fias_code = models.CharField("Код ФИАС", max_length=50, blank=True, null=True)
    district_code = models.CharField("Код района", max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = "Район"
        verbose_name_plural = "Районы"
        ordering = ["name"]
        unique_together = ("region", "name")

    def __str__(self):
        return f"{self.region} – {self.name}"


# ---------- КОНТРАКТ (основная модель) ----------


class Contract(models.Model):
    # аналогично Work
    TYPE_ONEOFF_LICENSEE = "oneoff_licensee"
    TYPE_LONGTERM_TO_LICENSEE = "longterm_to_licensee"
    TYPE_ONEOFF_LAB = "oneoff_lab"

    TYPE_CHOICES = (
        (TYPE_ONEOFF_LICENSEE, "Разовый (лицензиат)"),
        (TYPE_LONGTERM_TO_LICENSEE, "Долгосрочный ТО (лицензиат)"),
        (TYPE_ONEOFF_LAB, "Разовый (лаборатория)"),
    )

    # Служебные флаги
    is_trash = models.BooleanField("В корзине", default=False, db_index=True)
    is_archived = models.BooleanField("В архиве", default=False, db_index=True)

    # Основные сведения
    type = models.CharField("Тип договора", max_length=25, choices=TYPE_CHOICES, db_index=True)
    number = models.CharField("Номер договора", max_length=50, blank=True)
    date_concluded = models.DateField("Дата заключения", blank=True, null=True)
    customer = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        limit_choices_to={"is_customer": True},
        related_name="contracts_customer",
        verbose_name="Заказчик",
        null=True,
        blank=True,
    )
    date_start = models.DateField("Начало действия")
    date_end = models.DateField("Окончание действия")
    # исполнитель
    executor = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name="Исполнитель",
        related_name="contracts_executor",
        null=True,
        blank=True,
    )
    note = models.TextField("Примечание", blank=True)

    # ---------- ЧЕК-ЛИСТ: СИСТЕМЫ ----------
    gos_services = models.DateField(blank=True, null=True, verbose_name="Госуслуги")
    oko          = models.DateField(blank=True, null=True, verbose_name="ОКО")
    spolokh      = models.DateField(blank=True, null=True, verbose_name="Сполох")

    # ---------- ЧЕК-ЛИСТ: СТАДИЯ ПОДПИСАНИЯ ----------
    contract_to_be_signed              = models.BooleanField(default=True, verbose_name="На подписании")
    contract_signed                    = models.BooleanField(default=False, verbose_name="Подписан")
    contract_signed_in_trading_platform= models.BooleanField(default=False, verbose_name="Торги")
    contract_signed_in_EDO             = models.BooleanField(default=False, verbose_name="ЭДО")
    contract_original_received         = models.BooleanField(default=False, verbose_name="Бумажный оригинал")
    contract_termination               = models.BooleanField(default=False, verbose_name="Расторжение")

    # Файлы (1 шт., необязательные)
    file = models.FileField(
        "Файл договора",
        upload_to="contracts/%Y/%m/",
        blank=True,
        validators=[file_validator],
        help_text="Любой формат, кроме .exe и пр. До 100 МБ",
    )

    # Финансы
    total_sum = models.DecimalField("Сумма контракта общая", max_digits=12, decimal_places=2, default=0.00)
    monthly_sum = models.DecimalField("Сумма контракта в месяц", max_digits=12, decimal_places=2, default=0.00)
    advance = models.DecimalField("Аванс", max_digits=12, decimal_places=2, default=0.00)

    # Статус
    STATUS_PENDING = "pending"               # ожидание
    STATUS_ACTIVE = "active"                 # действует
    STATUS_ACTIVE_EXPIRES = "active_expires" # истекает
    STATUS_ACTIVE_EXPIRED = "active_expired" # истёк
    STATUS_COMPLETED = "completed"            # завершён

    STATUS_CHOICES = (
        (STATUS_PENDING, "Ожидание"),
        (STATUS_ACTIVE, "Действует"),
        (STATUS_ACTIVE_EXPIRES, "Истекает"),
        (STATUS_ACTIVE_EXPIRED, "Истёк"),
        (STATUS_COMPLETED, "Завершён"),
    )
    status = models.CharField(
        "Статус", max_length=15, choices=STATUS_CHOICES,
        default=STATUS_PENDING, db_index=True)

    # Акт итоговый
    final_act_date = models.DateField("Дата итогового акта", blank=True, null=True)
    final_act_present = models.BooleanField("Итоговый акт сформирован", default=False, editable=False)

    # Служебные
    created_at = models.DateTimeField("Создан", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)
    creator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Автор", related_name="contracts_created")

    # менеджер
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

    # --------- служебные методы ---------
    def save(self, *args, **kwargs):
        self._recalc_status()  # рассчитаем перед сохранением
        super().save(*args, **kwargs)

    def _recalc_status(self):
        """Рассчитать статус по алгоритму."""
        settings = get_contract_settings()
        today = timezone.now().date()
        start, end = self.date_start, self.date_end

        # 1. Долгосрочный ТО (лицензиат)
        if self.type == self.TYPE_LONGTERM_TO_LICENSEE:
            if today < start:
                self.status = self.STATUS_PENDING
            elif today > end:
                self.status = self.STATUS_COMPLETED
            else:  # внутри срока
                days_left = (end - today).days
                self.status = (
                    self.STATUS_ACTIVE_EXPIRES
                    if days_left <= settings.days_before_expires
                    else self.STATUS_ACTIVE
                )
            return

        # 2. Разовые (лицензиат или лаборатория)
        if self.type in (self.TYPE_ONEOFF_LICENSEE, self.TYPE_ONEOFF_LAB):
            if self.final_act_present:
                self.status = self.STATUS_COMPLETED
                return
            if today < start:
                self.status = self.STATUS_PENDING
            elif today > end:
                self.status = self.STATUS_ACTIVE_EXPIRED
            else:
                days_left = (end - today).days
                self.status = (
                    self.STATUS_ACTIVE_EXPIRES
                    if days_left <= settings.days_before_expires
                    else self.STATUS_ACTIVE
                )

    # --------- представления ---------
    def __str__(self):
        return f"{self.number or 'б/н'} ({self.get_type_display()})"



    # ---------- helper-свойства для шаблонов / логики ----------
    # @property
    # def is_longterm(self):
    #     """Долгосрочный ли договор (по типу)."""
    #     return self.type in (self.TYPE_LONGTERM_TO_LICENSEE, self.TYPE_LONGTERM_LAB, self.TYPE_SMR_LICENSEE)
    #
    # @property
    # def company_kind(self):
    #     """Вид компании-исполнителя (для фильтров)."""
    #     return self.executor.is_licensee if self.executor else None


# ---------- СВЯЗАННЫЕ МОДЕЛИ ----------


class InterimAct(models.Model):
    """Промежуточный этапный акт (много штук к одному договору)."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="interim_acts")
    title = models.CharField("Название", max_length=50, default="Этап Акт")
    date = models.DateField("Дата")
    file = models.FileField(
        "Файл акта",
        upload_to="acts/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx", "jpg", "jpeg", "png"])],
        help_text="Не более 20 МБ",
    )

    class Meta:
        verbose_name = "Промежуточный акт"
        verbose_name_plural = "Промежуточные акты"
        ordering = ["date"]

    def __str__(self):
        return f"{self.title} от {self.date} (договор {self.contract.number or 'б/н'})"


class ProtectionObject(models.Model):
    """Объект защиты (много штук к одному договору)."""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="objects")
    name = models.CharField("Наименование", max_length=255)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name="Регион", related_name="objects")
    district = models.ForeignKey(District, on_delete=models.PROTECT, verbose_name="Район", related_name="objects")
    address = models.TextField("Адрес")
    contacts = models.TextField("Контакты", blank=True)
    # субподрядчик
    subcontractor = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        limit_choices_to={"is_subcontractor": True},
        verbose_name="Субподрядчик",
        blank=True,
        null=True,
        related_name="protection_objects_sub",
    )
    # финансы субподрядчик
    total_sum_subcontract = models.DecimalField("Сумма субконтракта общая", max_digits=12, decimal_places=2, default=0.00)
    monthly_sum_subcontract = models.DecimalField("Сумма субконтракта в месяц", max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Объект защиты"
        verbose_name_plural = "Объекты защиты"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.region} – {self.district})"


class Ak(models.Model):
    """Абонентский комплект (много-ко-многим к объектам защиты + регион/район)."""
    # связь M2M с ProtectionObject (чтобы один и тот же АК мог висеть у разных объектов)
    protection_objects = models.ManyToManyField(
        ProtectionObject,
        related_name="aks",
        verbose_name="Объекты защиты",
        blank=True,
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        verbose_name="Регион установки",
        null=True,
        blank=True,
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        verbose_name="Район установки",
        null=True,
        blank=True,
    )

    number = models.PositiveIntegerField(
        "Номер АК",
        validators=[MinValueValidator(1), MaxValueValidator(99999999)],
        help_text="Макс. 8 цифр",
    )
    name = models.CharField("Наименование", max_length=255)
    address = models.TextField("Адрес установки")

    # защита от физического удаления – запретим в админке / signals
    class Meta:
        verbose_name = "Абонентский комплект (АК)"
        verbose_name_plural = "Абонентские комплекты (АК)"
        unique_together = ("number", "region", "district")   # уникальность по номеру + регион + район
        ordering = ["number"]

        # быстрый поиск по номеру + регион/район
        indexes = [
            models.Index(fields=["number"], name="ak_number_idx"),
            models.Index(fields=["region", "district"], name="ak_region_district_idx"),
        ]

    def __str__(self):
        return f"АК №{self.number} – {self.name}"
