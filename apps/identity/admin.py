# apps/identity/admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Prefetch
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User, Employee, ManagerPermission, UserCategory


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 1
    autocomplete_fields = ('company',)


class ManagerPermissionInline(admin.StackedInline):
    model = ManagerPermission
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    def get_inlines(self, request, obj=None):
        if obj is None:
            return [EmployeeInline]

        if obj.category == UserCategory.MANAGER:
            return [EmployeeInline, ManagerPermissionInline]
        return [EmployeeInline]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(BaseUserAdmin.fieldsets[:2])

        fieldsets.append(
            (_('Дополнительная информация'), {
                'fields': ('category', 'phone', 'avatar', 'news_is_active'),
            }),
        )

        if request.user.is_superuser:
            fieldsets.append(
                (_('Группы Django (только для отладки)'), {
                    'fields': ('groups', 'user_permissions'),
                    'classes': ('collapse',),
                }),
            )

        fieldsets.append(
            (_('Важные даты'), {'fields': ('last_login', 'date_joined')}),
        )

        return fieldsets

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {
            'fields': ('category', 'phone', 'news_is_active'),
        }),
    )

    list_display = BaseUserAdmin.list_display + ('category', 'phone', 'get_companies', 'is_system')
    list_filter = BaseUserAdmin.list_filter + ('category', 'is_system', 'news_is_active')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            Prefetch('employees', queryset=Employee.objects.select_related('company'))
        )

    @admin.display(description=_('Компании'))
    def get_companies(self, obj):
        companies = obj.employees.select_related('company').all()
        if not companies:
            return '-'

        names = []
        for emp in companies[:2]:
            status = '✓' if emp.is_active else '✗'
            names.append(f'{status} {emp.company.name}')

        result = ', '.join(names)
        if companies.count() > 2:
            result += f' (+{companies.count() - 2})'

        return format_html(result)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if 'category' in form.changed_data:
            messages.info(
                request,
                f"Категория изменена на '{obj.get_category_display()}'. "
                f"Группы Django автоматически синхронизированы."
            )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'company__name')
    autocomplete_fields = ('user', 'company')