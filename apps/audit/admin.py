# apps/audit/admin.py
from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("contract", "event_type", "user", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("contract__number", "user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)