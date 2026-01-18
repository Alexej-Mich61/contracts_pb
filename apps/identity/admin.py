#apps/identity/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Employee



class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 0
    fields = ("company", "role", "is_active")
    raw_id_fields = ("company",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    readonly_fields = ("is_system",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Категория и права", {
            "fields": (
                "category",
                "can_view_systems",
                "can_edit_systems",
                "can_edit_sign_stage",
                "can_delete_contract",
            )
        }),
        ("Контакт и аватар", {
            "fields": ("phone", "avatar")
        }),
    )

    list_display = (
        "username",
        "email",
        "phone",
        "category",
        "is_staff",
        "is_system",
    )
    list_filter = BaseUserAdmin.list_filter + ("category",)

    inlines = [EmployeeInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "is_active")
    list_filter = ("role", "is_active", "company__is_licensee")
    search_fields = ("user__username", "company__name")