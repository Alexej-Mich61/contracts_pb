# apps/contract_core/signals.py
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import PermissionDenied
from .models import Ak

@receiver(pre_delete, sender=Ak)
def protect_ak_from_delete(sender, instance, **kwargs):
    if instance.protection_objects.exists():
        raise PermissionDenied(
            "Нельзя удалить АК, который привязан к объектам защиты. "
            "Сначала отвяжите его от всех объектов."
        )