# apps/identity/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .models import User, Employee
from apps.contract_core.models import Company


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 1
    fields = ('company', 'is_active', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = "Сотрудник компании"
    verbose_name_plural = "Сотрудники компании"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Фильтруем компании только исполнителей (лицензиат или лаборатория).
        """
        if db_field.name == 'company':
            kwargs['queryset'] = Company.objects.filter(
                Q(is_licensee=True) | Q(is_laboratory=True)
            ).order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'email',
        'get_full_name',
        'category',
        'phone',
        'news_is_active',
        'is_active',
        'is_system',
        'date_joined'
    )
    list_filter = (
        'category',
        'is_active',
        'is_staff',
        'is_superuser',
        'is_system',
        'news_is_active'
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Персональная информация'), {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'avatar')
        }),
        (_('Категория и статус рассылки'), {
            'fields': ('category', 'news_is_active', 'is_system')
        }),
        (_('Дополнительные права для менеджера'), {
            'fields': (
                'can_mark_final_act',
                'can_edit_system_checklist',
                'can_edit_signing_stages',
                'can_edit_interim_act',
            ),
            'classes': ('collapse',),  # сворачиваемый блок
        }),
        (_('Права и группы'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Важные даты'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2',
                'category', 'news_is_active', 'phone'
            ),
        }),
    )

    inlines = [EmployeeInline]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
    get_full_name.short_description = "Имя / Логин"

    def get_readonly_fields(self, request, obj=None):
        """
        Запрещаем редактировать системные поля для обычных пользователей.
        """
        readonly = ['is_system', 'date_joined', 'last_login']
        if obj and obj.is_system:
            readonly += ['category', 'username', 'news_is_active']
        return readonly


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'company__is_licensee', 'company__is_laboratory')
    search_fields = ('user__username', 'user__email', 'company__name', 'company__inn')
    ordering = ('-created_at',)
    raw_id_fields = ('user', 'company')