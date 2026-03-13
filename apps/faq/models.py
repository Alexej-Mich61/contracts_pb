# apps/faq/models.py
import os
from pathlib import Path
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.contract_core.services.uuid_path_generator import faq_file_path
from apps.contract_core.validators import file_validator




class FAQItem(models.Model):
    """Вопрос-ответ для FAQ."""

    question = models.CharField(_("вопрос"), max_length=500)
    answer = models.TextField(_("ответ"))
    order = models.PositiveIntegerField(_("порядок"), default=0, db_index=True)
    is_active = models.BooleanField(_("активен"), default=True, db_index=True)
    created_at = models.DateTimeField(_("создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("обновлен"), auto_now=True)

    class Meta:
        verbose_name = _("вопрос-ответ")
        verbose_name_plural = _("вопросы и ответы")
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.question[:50]

    def get_absolute_url(self):
        return reverse("faq:item_detail", kwargs={"pk": self.pk})


class FAQFile(models.Model):
    """Полезные файлы для FAQ."""

    title = models.CharField(_("название"), max_length=255, blank=True)
    file = models.FileField(
        _("файл"),
        upload_to=faq_file_path,  # <-- Используем новый генератор
        validators=[file_validator],
    )
    description = models.TextField(_("описание"), blank=True)
    uploaded_at = models.DateTimeField(_("загружен"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("файл FAQ")
        verbose_name_plural = _("файлы FAQ")
        ordering = ["-id"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.title:
            return f"{self.title}{self.extension}"
        return self.filename

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lower()

    def get_absolute_url(self):
        return reverse("faq:file_download", kwargs={"pk": self.pk})