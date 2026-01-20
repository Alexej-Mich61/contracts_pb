# apps/companies/admin.py
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .resources import CompanyResource
from .models import Company
from apps.identity.models import Employee



class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0
    raw_id_fields = ("user",)          # удобный поиск пользователя
    fields = ("user", "role", "is_active",
              "can_delete_contract", "can_edit_systems", "can_edit_sign_stage")

# 2. Админка
@admin.register(Company)
class CompanyAdmin(ImportExportModelAdmin):
    resource_class = CompanyResource  # подключаем импорт/экспорт

    list_display = ("name", "inn", "fias_code", "roles_list")
    list_filter = ("is_customer", "is_licensee", "is_lab", "is_subcontractor")
    search_fields = ("name", "inn")
    ordering = ("name",)

    # отображаем роли чек-боксами
    fields = (
        "name",
        "inn",
        "fias_code",
        "is_customer",
        "is_licensee",
        "is_lab",
        "is_subcontractor",
    )

    def roles_list(self, obj):
        # короткая строка для list_display
        roles = []
        if obj.is_customer:
            roles.append("Заказчик")
        if obj.is_licensee:
            roles.append("Лицензиат")
        if obj.is_lab:
            roles.append("Лаборатория")
        if obj.is_subcontractor:
            roles.append("Субподрядчик")
        return ", ".join(roles) or "-"

    roles_list.short_description = "Роли"

    # Добавляем текстовую подсказку в админ
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_help'] = (
            "Для импорта компаний используйте таблицу с колонками в порядке: name, inn, is_customer, is_licensee, is_lab, is_subcontractor. "
            "name и inn обязательны. Хотя бы одна роль должна быть True. ИНН проверяется на корректность и уникальность."
        )
        return super().changelist_view(request, extra_context)
