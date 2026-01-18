# apps/chat/admin.py
from django.contrib import admin
from .models import UserChatSettings, Dialogue, Message


@admin.register(UserChatSettings)
class UserChatSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "is_sound_enabled", "volume")
    list_filter = ("is_sound_enabled",)
    search_fields = ("user__username",)


@admin.register(Dialogue)
class DialogueAdmin(admin.ModelAdmin):
    list_display = ("participant1", "participant2", "is_sound_on", "created_at")
    list_filter = ("is_sound_on", "created_at")
    search_fields = ("participant1__username", "participant2__username")
    readonly_fields = ("created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("dialogue", "sender", "short_text", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("text", "sender__username")

    def short_text(self, obj):
        return obj.text[:50]

    short_text.short_description = "Текст"