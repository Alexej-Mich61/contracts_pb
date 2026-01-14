#apps/audit/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from apps.contract_core.models import Contract
from .models import Log


print("SIGNALS IMPORTED")   # ← должно появиться

# @receiver(post_save, sender=Contract)
# def log_contract_change(sender, instance, created, **kwargs):
#     print("SENDER:", sender, type(sender))
#     print("SENDER.OBJECTS:", sender.objects, type(sender.objects))
#     print("SIGNAL FIRED", created)
#
#     if created:
#         for field in sender._meta.fields:
#             value = getattr(instance, field.name)
#             Log.objects.create(
#                 contract=instance,
#                 user=instance.creator,
#                 field=field.verbose_name or field.name,
#                 old_value="",
#                 new_value=str(value),
#             )
#         return
#
#     if instance.pk is None:
#         return
#
#     try:
#         old = sender.objects.get(pk=instance.pk)
#     except sender.DoesNotExist:
#         return
#
#     for field in sender._meta.fields:
#         print("FIELD:", field.name, "SENDER:", sender, "sender.objects:", sender.objects)
#         old_val = getattr(old, field.name)
#         new_val = getattr(instance, field.name)
#         if old_val != new_val:
#             print("LOGGING", field.name, old_val, "→", new_val)
#             Log.objects.create(
#                 contract=instance,
#                 user=instance.creator,
#                 field=field.verbose_name or field.name,
#                 old_value=str(old_val),
#                 new_value=str(new_val),
#             )