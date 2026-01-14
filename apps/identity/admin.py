#apps/identity/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User



@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # поля, которые НЕ редактируем вручную
    readonly_fields = ("is_system",)  # ← добавьте

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Контакт", {"fields": ("phone",)}),  # ← убрали is_system отсюда
    )
    list_display = ("username", "email", "phone", "is_staff", "is_system")
    list_filter = BaseUserAdmin.list_filter + ("is_system",)