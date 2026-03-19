# apps/contract_core/admin.py
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin



from .models import (
    ContractSettings, Region, District, Work, Company,
    SigningStage, ContractSigningStage, SystemType,
    ContractSystemCheck, Contract, FinalAct, InterimAct,
    ProtectionObject, Ak
)
from .resources import CompanyResource, AkResource
from auditlog.models import LogEntry
from auditlog.admin import LogEntryAdmin as BaseLogEntryAdmin



# Отменяем старую регистрацию
admin.site.unregister(LogEntry)


@admin.register(LogEntry)
class LogEntryAdmin(BaseLogEntryAdmin):
    # Добавляем ID и другие поля в список
    list_display = [
        'id',  # ID записи лога
        'timestamp',  # Created
        'actor',  # Пользователь
        'action',  # Action
        'object_pk',  # ID объекта
        'content_type',  # Ресурс (модель)
        'changes',  # Changes
        #'correlation_id',
    ]

    # Фильтры
    list_filter = [
        'action',
        'content_type',
        'timestamp',
    ]

    # Поиск
    search_fields = [
        'id',
        'object_pk',  # Поиск по ID объекта
        'object_repr',  # Поиск по строковому представлению
        'actor__username',
        'actor__first_name',
        'actor__last_name',
    ]

    # Сделаем ссылки кликабельными
    list_display_links = ['id', 'timestamp', 'object_pk', 'content_type',]


# ---------- ИНЛАЙНЫ ----------
class FinalActInline(admin.StackedInline):
    model = FinalAct
    extra = 0
    can_delete = False
    fields = ('present', 'date', 'file', 'note', 'checked_by', 'checked_at')
    readonly_fields = ('checked_by', 'checked_at')
    verbose_name = "Итоговый акт"
    verbose_name_plural = "Итоговые акты"


class InterimActInline(admin.TabularInline):
    model = InterimAct
    extra = 1
    fields = ('title', 'date', 'file')
    verbose_name = "Промежуточный акт"
    verbose_name_plural = "Промежуточные акты"



class ContractSigningStageInline(admin.StackedInline):
    model = ContractSigningStage
    extra = 0
    can_delete = False
    fields = ('stage', 'changed_at', 'changed_by', 'note')
    readonly_fields = ('changed_at', 'changed_by')
    verbose_name = "Стадия подписания (по договору)"
    verbose_name_plural = "Стадии подписания (по договору)"


class ContractSystemCheckInline(admin.TabularInline):
    model = ContractSystemCheck
    extra = 0
    fields = ('system_type', 'last_checked', 'checked_by', 'note')
    readonly_fields = ('checked_by',)
    verbose_name = "Проверка системы (чек-лист конкретного договора)"
    verbose_name_plural = "Проверки систем (чек-лист конкретного договора)"


class ProtectionObjectInline(admin.TabularInline):
    model = ProtectionObject
    extra = 1
    fields = ('name', 'district', 'address', 'contacts', 'subcontractor',
              'total_sum_subcontract', 'monthly_sum_subcontract')
    verbose_name = "Объект защиты"
    verbose_name_plural = "Объекты защиты"


# Новый инлайн для АК внутри объекта защиты
class AkInline(admin.TabularInline):
    model = ProtectionObject.aks.through  # ← через related_name
    extra = 1
    verbose_name = "Абонентский комплект"
    verbose_name_plural = "Абонентские комплекты"

    # Поля, которые показываем в инлайне
    fields = ('ak',)

    # Автодополнение с поиском
    autocomplete_fields = ['ak']



# ---------- АДМИНКИ ----------

@admin.register(ContractSettings)
class ContractSettingsAdmin(admin.ModelAdmin):
    list_display = ('days_before_expires', 'longterm_status_time', 'oneoff_status_time')
    readonly_fields = ('pk',)
    fieldsets = (
        (None, {
            'fields': ('days_before_expires', 'longterm_status_time', 'oneoff_status_time')
        }),
    )


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'fias_code', 'region_code')
    search_fields = ('name', 'fias_code')


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'region')
    list_filter = ('region',)
    search_fields = ('name', 'region__name')


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ('name', 'work_type', 'is_active', 'description')
    list_filter = ('work_type', 'is_active')
    search_fields = ('name', 'description')  # добавлен поиск по описанию
    # Если нужно показывать описание в форме редактирования:
    fields = ('name', 'work_type', 'is_active', 'description')


@admin.register(Company)
class CompanyAdmin(ImportExportModelAdmin):
    resource_class = CompanyResource
    list_display = (
        'name',
        'inn',
        'email',  # добавлено
        'phone',  # добавлено
        'is_customer',
        'is_licensee',
        'is_laboratory',
        'is_subcontractor',
        'notification_agreed'
    )
    list_filter = (
        'is_customer',
        'is_licensee',
        'is_laboratory',
        'is_subcontractor',
        'notification_agreed'
    )
    search_fields = ('name', 'inn', 'email', 'phone')  # добавлен поиск

    # Добавляем в форму редактирования (fieldsets)
    fieldsets = (
        (None, {
            'fields': ('name', 'inn', 'email', 'phone')  # или добавь в существующий блок
        }),
        ('Роли', {
            'fields': ('is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor')
        }),
        ('Уведомления', {
            'fields': ('notification_agreed',)
        }),
        ('Адрес', {
            'fields': ('fias_code',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_licensee', 'mark_as_laboratory', 'mark_notification_agreed']

    def mark_as_licensee(self, request, queryset):
        queryset.update(is_licensee=True)

    mark_as_licensee.short_description = "Отметить как лицензиат МЧС"

    def mark_as_laboratory(self, request, queryset):
        queryset.update(is_laboratory=True)

    mark_as_laboratory.short_description = "Отметить как лаборатория"

    def mark_notification_agreed(self, request, queryset):
        queryset.update(notification_agreed=True)

    mark_notification_agreed.short_description = "Отметить 'Согласие на уведомление'"


@admin.register(SigningStage)
class SigningStageAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'is_final', 'description')
    ordering = ('order', 'name')
    search_fields = ('name', 'slug', 'description')


@admin.register(SystemType)
class SystemTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')


@admin.register(Contract)
class ContractAdmin(ImportExportModelAdmin):
    list_display = ('number', 'type', 'status', 'customer', 'executor', 'date_start', 'date_end')
    list_filter = ('type', 'status', 'is_trash', 'is_archived')
    search_fields = ('number', 'customer__name', 'executor__name')
    ordering = ('-created_at',)
    inlines = [
        FinalActInline,
        InterimActInline,
        ContractSigningStageInline,
        ContractSystemCheckInline,
        ProtectionObjectInline,
    ]
    fieldsets = (
        ('Основное', {
            'fields': ('type', 'number', 'date_concluded', 'customer', 'date_start', 'date_end', 'executor', 'work')
        }),
        ('Финансы', {
            'fields': ('total_sum', 'monthly_sum', 'advance')
        }),
        ('Служебное', {
            'fields': ('status', 'is_trash', 'is_archived', 'creator', 'updater', 'created_at', 'updated_at')
        }),
        ('Примечание и файлы', {
            'fields': ('note', 'file')
        }),
    )
    readonly_fields = ('creator', 'updater', 'created_at', 'updated_at', 'status')


@admin.register(FinalAct)
class FinalActAdmin(admin.ModelAdmin):
    list_display = ('contract', 'present', 'date', 'checked_by', 'checked_at')
    list_filter = ('present',)
    search_fields = ('contract__number',)
    readonly_fields = ('checked_by', 'checked_at')


@admin.register(InterimAct)
class InterimActAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'contract')
    list_filter = ('date',)
    search_fields = ('title', 'contract__number')


@admin.register(ContractSigningStage)
class ContractSigningStageAdmin(admin.ModelAdmin):
    list_display = ('contract', 'stage', 'changed_at', 'changed_by')
    list_filter = ('stage',)
    search_fields = ('contract__number',)


@admin.register(ContractSystemCheck)
class ContractSystemCheckAdmin(admin.ModelAdmin):
    list_display = ('contract', 'system_type', 'last_checked', 'checked_by')
    list_filter = ('system_type', 'last_checked')
    search_fields = ('contract__number', 'system_type__name')


@admin.register(ProtectionObject)
class ProtectionObjectAdmin(admin.ModelAdmin):  # или твой HistoryAdminMixin
    list_display = ('name', 'contract', 'district', 'region_property', 'subcontractor')
    list_filter = ('district__region', 'subcontractor')
    search_fields = ('name', 'address', 'contract__number')

    inlines = [AkInline]  # ← добавляем

    def region_property(self, obj):
        return obj.region

    region_property.short_description = "Регион"


@admin.register(Ak)
class AkAdmin(ImportExportModelAdmin):
    resource_class = AkResource
    list_display = ('number', 'name', 'district', 'region_property')
    list_filter = ('district__region',)
    search_fields = ('number', 'name', 'address', 'district__name')  # ← поиск по району тоже
    autocomplete_fields = []  # если нужно, можно добавить

    def region_property(self, obj):
        return obj.region

    region_property.short_description = "Регион"

