#apps/contract_works/admin.py
from django.contrib import admin
from .models import Work, ContractWork

# Справочник работ
@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("name", "work_type")
    list_filter = ("work_type",)
    search_fields = ("name",)
    ordering = ("name",)

# Инлайн-работы внутри договора (если хотите)
class ContractWorkInline(admin.TabularInline):
    model = ContractWork
    extra = 1
    fields = ("work",)
    verbose_name = "Работа"
    verbose_name_plural = "Работы"