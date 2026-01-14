# apps/companies/admin.py
from django.contrib import admin
from .models import Company, Employee




class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0
    raw_id_fields = ("user",)          # удобный поиск пользователя
    fields = ("user", "role", "is_active",
              "can_delete_contract", "can_edit_systems", "can_edit_sign_stage")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "inn")
    list_filter = ("kind",)
    search_fields = ("name", "inn")
    ordering = ("name",)
    inlines = [EmployeeInline]

