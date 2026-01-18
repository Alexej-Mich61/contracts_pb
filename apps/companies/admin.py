# apps/companies/admin.py
from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import CharWidget
from .models import Company
from apps.identity.models import Employee




# 1. Ресурс для импорта
class CompanyResource(resources.ModelResource):
    """Импорт только 3 колонок: название, инн, код фиас."""
    name = fields.Field(attribute="name", column_name="название")
    inn = fields.Field(attribute="inn", column_name="инн", widget=CharWidget())
    fias_code = fields.Field(attribute="fias_code", column_name="код_фиас")

    class Meta:
        model = Company
        import_id_fields = ("inn",)  # если ИНН совпал – обновляем, иначе создаём
        skip_unchanged = True
        fields = ("name", "inn", "fias_code")

    def before_import_row(self, row, **kwargs):
        # значения ролей по умолчанию при импорте
        row.setdefault("is_customer", True)
        row.setdefault("is_licensee", False)
        row.setdefault("is_lab", False)
        row.setdefault("is_subcontractor", False)



class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0
    raw_id_fields = ("user",)          # удобный поиск пользователя
    fields = ("user", "role", "is_active",
              "can_delete_contract", "can_edit_systems", "can_edit_sign_stage")

# 2. Админка
@admin.register(Company)
class CompanyAdmin(ImportExportModelAdmin):
    resource_classes = [CompanyResource]  # подключаем импорт/экспорт

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
