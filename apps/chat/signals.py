# apps/chat/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserChatSettings, UserOnlineStatus

User = get_user_model()


@receiver(post_save, sender=User)
def create_chat_settings(sender, instance, created, **kwargs):
    if created:
        UserChatSettings.objects.get_or_create(user=instance)
        UserOnlineStatus.objects.get_or_create(user=instance)