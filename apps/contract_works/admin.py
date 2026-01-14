#apps/contract_works/admin.py
from django.contrib import admin
from .models import Work


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("name", "work_type", "company_kind")
    list_filter = ("work_type", "company_kind")
    search_fields = ("name",)
    ordering = ("name",)