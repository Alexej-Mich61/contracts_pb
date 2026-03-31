# apps/identity/admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.db.models import Prefetch, Count, Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django import forms

from .models import User, Employee, ManagerPermission, UserCategory


class EmployeeInline(admin.TabularInline):
    model = Employee
    extra = 1
    autocomplete_fields = ('company',)


class ManagerPermissionInline(admin.StackedInline):
    model = ManagerPermission
    can_delete = False
    verbose_name = _("Права менеджера")
    verbose_name_plural = _("Права менеджера")

    fieldsets = (
        (_("Договоры"), {
            'fields': (
                'can_add_contract',
                'can_edit_contract_main_fields',
                'can_edit_signing_stages',
                'can_edit_system_checklist',
                'can_mark_final_act',
                'can_edit_interim_act',
            ),
            'classes': ('collapse',),
        }),
        (_("Справочники"), {
            'fields': (
                'can_manage_companies',
                'can_manage_aks',
            ),
            'classes': ('collapse',),
        }),
        (_("Служебная информация"), {
            'fields': ('updated_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('updated_at',)


class CustomUserCreationForm(UserCreationForm):
    """
    Форма создания пользователя.
    Явно объявляем email, чтобы гарантировать его наличие в форме.
    """
    email = forms.EmailField(
        label=_("Email"),
        required=True,
        help_text=_("Обязательное поле")
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'category', 'phone', 'news_is_active')

    def clean_email(self):
        """Валидация email."""
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError(_("Email обязателен для заполнения"))
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Пользователь с таким email уже существует"))
        return email


class CustomUserChangeForm(UserChangeForm):
    """
    Форма редактирования пользователя.
    """

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        is_system = cleaned_data.get('is_system')

        if is_system and category != UserCategory.GUEST:
            raise forms.ValidationError(
                _("Системный пользователь должен иметь категорию 'Гость'")
            )

        return cleaned_data


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    CATEGORY_ICONS = {
        UserCategory.ADMIN: '👑',
        UserCategory.MANAGER: '👔',
        UserCategory.GUEST: '👤',
    }

    def get_inlines(self, request, obj=None):
        if obj is None:
            return [EmployeeInline]

        if obj.category == UserCategory.MANAGER:
            return [EmployeeInline, ManagerPermissionInline]
        return [EmployeeInline]

    def get_fieldsets(self, request, obj=None):
        # ИСПРАВЛЕНИЕ: При создании возвращаем add_fieldsets
        if obj is None:
            return self.add_fieldsets

        # При редактировании
        fieldsets = list(BaseUserAdmin.fieldsets[:2])

        fieldsets.append(
            (_('Категория и контакты'), {
                'fields': ('category', 'phone', 'avatar', 'news_is_active'),
            }),
        )

        if request.user.is_superuser:
            fieldsets.append(
                (_('⚠️ Группы Django (только для отладки)'), {
                    'fields': ('groups', 'user_permissions'),
                    'classes': ('collapse',),
                    'description': _(
                        'Внимание: группы синхронизируются автоматически на основе категории. '
                        'Ручное изменение может нарушить логику работы системы.'
                    ),
                }),
            )

        fieldsets.append(
            (_('Важные даты'), {'fields': ('last_login', 'date_joined')}),
        )

        if obj.is_system:
            fieldsets.insert(1, (
                _('Системный пользователь'), {
                'fields': ('is_system',),
                'description': _('Это системный пользователь. Нельзя изменить статус.'),
            }
            ))

        return fieldsets

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        (_('Категория и контакты'), {
            'fields': ('email', 'category', 'phone', 'news_is_active'),
        }),
    )

    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'get_category_display',
        'get_manager_summary',
        'get_companies_short',
        'is_active',
        'date_joined',
    )

    list_filter = (
        'is_active',
        'is_staff',
        'news_is_active',
        'category',
    )

    list_select_related = ('manager_permissions',)
    list_per_page = 50

    search_fields = (
        'username',
        'first_name',
        'last_name',
        'email',
        'phone',
        'employments__company__name',
    )

    actions = ['make_admin', 'make_manager', 'make_guest', 'activate_news', 'deactivate_news']

    readonly_fields = ('last_login', 'date_joined')

    def get_queryset(self, request):
        qs = super().get_queryset(request).prefetch_related(
            Prefetch(
                'employments',
                queryset=Employee.objects.select_related('company').filter(is_active=True)
            )
        ).annotate(
            companies_count=Count('employments', filter=Q(employments__is_active=True))
        )
        return qs

    @admin.display(description=_('Категория'), ordering='category')
    def get_category_display(self, obj):
        icon = self.CATEGORY_ICONS.get(obj.category, '')
        return f"{icon} {obj.get_category_display()}"

    @admin.display(description=_('Права менеджера'))
    def get_manager_summary(self, obj):
        if not obj.is_manager:
            return '-'

        perms = obj.manager_permissions
        icons = []

        if perms.can_add_contract:
            icons.append('➕')
        if perms.can_edit_contract_main_fields:
            icons.append('✏️')
        if perms.can_manage_companies:
            icons.append('🏢')
        if perms.can_manage_aks:
            icons.append('📦')

        return format_html(
            '<span title="{}">{}</span>',
            f"Договоры: {perms.can_add_contract}/{perms.can_edit_contract_main_fields}, "
            f"Компании: {perms.can_manage_companies}, АК: {perms.can_manage_aks}",
            ' '.join(icons) if icons else '⚠️ Нет прав'
        )

    @admin.display(description=_('Компании'))
    def get_companies_short(self, obj):
        employments = list(obj.employments.all()[:3])
        if not employments:
            return '-'

        names = []
        for emp in employments[:2]:
            status = '🟢' if emp.is_active else '🔴'
            names.append(f'{status} {emp.company.name}')

        result = ', '.join(names)
        if obj.companies_count > 2:
            result += f' (+{obj.companies_count - 2})'

        return format_html(result)

    def save_model(self, request, obj, form, change):
        old_category = None
        if change:
            old_category = User.objects.get(pk=obj.pk).category

        super().save_model(request, obj, form, change)

        if change and 'category' in form.changed_data and old_category:
            messages.info(
                request,
                _(f"Категория изменена с '{dict(UserCategory.CHOICES)[old_category]}' "
                  f"на '{obj.get_category_display()}'. "
                  f"Группы Django и права менеджера автоматически синхронизированы.")
            )

            if obj.category == UserCategory.MANAGER:
                messages.warning(
                    request,
                    _("Не забудьте настроить права менеджера во вкладке 'Права менеджера'")
                )

    @admin.action(description=_('Сделать Администраторами'))
    def make_admin(self, request, queryset):
        updated = queryset.update(category=UserCategory.ADMIN)
        for user in queryset:
            user.save(update_fields=['category'])
        self.message_user(request, f'{updated} пользователей назначены Администраторами')

    @admin.action(description=_('Сделать Менеджерами'))
    def make_manager(self, request, queryset):
        updated = queryset.update(category=UserCategory.MANAGER)
        for user in queryset:
            user.save(update_fields=['category'])
        self.message_user(
            request,
            f'{updated} пользователей назначены Менеджерами. '
            f'Не забудьте настроить их права.'
        )

    @admin.action(description=_('Сделать Гостями'))
    def make_guest(self, request, queryset):
        updated = queryset.update(category=UserCategory.GUEST)
        for user in queryset:
            user.save(update_fields=['category'])
        self.message_user(request, f'{updated} пользователей назначены Гостями')

    @admin.action(description=_('Активировать рассылку'))
    def activate_news(self, request, queryset):
        updated = queryset.update(news_is_active=True)
        self.message_user(request, f'Рассылка активирована для {updated} пользователей')

    @admin.action(description=_('Деактивировать рассылку'))
    def deactivate_news(self, request, queryset):
        updated = queryset.update(news_is_active=False)
        self.message_user(request, f'Рассылка деактивирована для {updated} пользователей')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'company__name')
    autocomplete_fields = ('user', 'company')
    date_hierarchy = 'created_at'


@admin.register(ManagerPermission)
class ManagerPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'get_user_category',
        'can_add_contract',
        'can_edit_contract_main_fields',
        'can_manage_companies',
        'can_manage_aks',
        'updated_at',
    )
    list_filter = (
        'can_add_contract',
        'can_edit_contract_main_fields',
        'can_manage_companies',
        'can_manage_aks',
        'updated_at',
    )
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    date_hierarchy = 'updated_at'

    @admin.display(description=_('Категория пользователя'))
    def get_user_category(self, obj):
        return obj.user.get_category_display()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')