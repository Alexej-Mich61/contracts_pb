#apps/audit/admin.py
from django.contrib import admin
from .models import Log


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ("contract", "field", "user", "timestamp")
    list_filter = ("timestamp", "user", "contract__type")
    search_fields = ("contract__number", "field", "user__username")
    readonly_fields = ("contract", "user", "field", "old_value", "new_value", "timestamp")
    ordering = ("-timestamp",)