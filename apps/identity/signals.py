# apps/identity/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from .models import User


@receiver(post_save, sender=User)
def sync_user_group(sender, instance, created, **kwargs):
    """
    При создании/изменении категории пользователя — синхронизируем с группой.
    """
    if not instance.category:
        return

    group_name = instance.category.capitalize()  # Admin → Admin, manager → Manager
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return

    # Удаляем из всех групп, кроме новой
    instance.groups.clear()
    instance.groups.add(group)