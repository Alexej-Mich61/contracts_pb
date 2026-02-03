# apps/contract_core/signals.py
from django.db.models.signals import pre_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import PermissionDenied
from .models import (
    Ak, Contract, ContractSigningStage, ContractSystemCheck,
    SigningStage, SystemType, FinalAct
)

@receiver(pre_delete, sender=Ak)
def protect_ak_from_delete(sender, instance, **kwargs):
    if instance.protection_objects.exists():
        raise PermissionDenied(
            "Нельзя удалить АК, который привязан к объектам защиты. "
            "Сначала отвяжите его от всех объектов."
        )

@receiver(post_save, sender=Contract)
def create_default_signing_stage(sender, instance, created, **kwargs):
    """Создаёт начальную стадию «На подписании» при создании договора."""
    if created:
        default_stage = SigningStage.objects.filter(slug='to_be_signed').first()
        if default_stage:
            ContractSigningStage.objects.create(
                contract=instance,
                stage=default_stage,
                changed_by=instance.creator if instance.creator else None
            )


@receiver(post_save, sender=Contract)
def create_system_checks(sender, instance, created, **kwargs):
    """Создаёт записи для всех активных систем при создании договора."""
    if created:
        active_systems = SystemType.objects.filter(is_active=True)
        for system in active_systems:
            ContractSystemCheck.objects.get_or_create(
                contract=instance,
                system_type=system
            )


@receiver(post_save, sender=Contract)
def create_final_act_on_contract_creation(sender, instance, created, **kwargs):
    """
    При создании договора автоматически создаётся пустая запись итогового акта.
    """
    if created:
        FinalAct.objects.get_or_create(contract=instance)