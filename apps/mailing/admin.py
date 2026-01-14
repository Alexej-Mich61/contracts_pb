# apps/mailing/admin.py
from django.contrib import admin
from .models import Recipient


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "email", "phone", "is_active")
    list_filter = ("is_active", "companies__kind", "created_at")
    search_fields = ("first_name", "last_name", "email", "companies__name")
    filter_horizontal = ("companies",)   # удобный виджет many-to-many