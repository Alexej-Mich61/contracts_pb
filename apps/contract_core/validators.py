# apps/contract_core/validators.py
import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.template.defaultfilters import filesizeformat





MAX_FILE_SIZE = 100 * 1024 * 1024        # 100 МБ
FORBIDDEN_EXT = {".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs"}

def file_validator(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext in FORBIDDEN_EXT:
        raise ValidationError(f"Запрещённый тип файла: {ext}")
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            f"Размер файла {filesizeformat(file.size)} превышает "
            f"допустимый {filesizeformat(MAX_FILE_SIZE)}"
        )



def inn_validator(value: int):
    s = str(value)
    if len(s) not in (10, 12):
        raise ValidationError(
            _("ИНН должен содержать 10 цифр (юрлицо) или 12 цифр (физлицо)."),
            params={"value": value},
        )
