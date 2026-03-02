# apps/chat/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import GlobalChatSettings, UserChatSettings, Dialogue, Message, UserOnlineStatus


@admin.register(GlobalChatSettings)
class GlobalChatSettingsAdmin(admin.ModelAdmin):
    """Админка для глобальных настроек (singleton)."""

    def has_add_permission(self, request):
        # Запрещаем добавление, если уже есть запись
        return not GlobalChatSettings.objects.filter(pk=1).exists()

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удаление
        return False

    def changelist_view(self, request, extra_context=None):
        # Перенаправляем сразу на редактирование единственной записи
        obj = GlobalChatSettings.get_instance()
        return self.changeform_view(
            request,
            object_id=str(obj.pk),
            extra_context=extra_context
        )

    list_display = ("default_sound", "updated_at")
    fields = ("default_sound",)


@admin.register(UserChatSettings)
class UserChatSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "is_sound_enabled", "volume", "has_custom_sound")
    list_filter = ("is_sound_enabled",)
    search_fields = ("user__username", "user__email")
    fields = ("user", "is_sound_enabled", "volume", "custom_sound")

    def has_custom_sound(self, obj):
        return bool(obj.custom_sound)

    has_custom_sound.boolean = True
    has_custom_sound.short_description = "Свой звук"


@admin.register(Dialogue)
class DialogueAdmin(admin.ModelAdmin):
    list_display = ("participant1", "participant2", "created_at", "updated_at", "message_count")
    list_filter = ("created_at",)
    search_fields = ("participant1__username", "participant2__username")
    readonly_fields = ("created_at", "updated_at")

    def message_count(self, obj):
        return obj.messages.count()

    message_count.short_description = "Сообщений"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("dialogue", "sender", "short_text", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("text", "sender__username", "dialogue__participant1__username")
    readonly_fields = ("created_at",)

    def short_text(self, obj):
        return obj.text[:50]

    short_text.short_description = "Текст"


@admin.register(UserOnlineStatus)
class UserOnlineStatusAdmin(admin.ModelAdmin):
    list_display = ("user", "is_online", "last_seen", "status_indicator")
    list_filter = ("is_online",)
    search_fields = ("user__username",)
    readonly_fields = ("last_seen",)

    def status_indicator(self, obj):
        color = "green" if obj.is_online else "gray"
        return format_html(
            '<span style="color: {};">●</span> {}',
            color,
            "Онлайн" if obj.is_online else "Оффлайн"
        )

    status_indicator.short_description = "Статус"