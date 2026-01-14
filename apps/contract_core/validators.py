#apps/contract_core/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def inn_validator(value: int):
    s = str(value)
    if len(s) not in (10, 12):
        raise ValidationError(
            _("ИНН должен содержать 10 цифр (юрлицо) или 12 цифр (физлицо)."),
            params={"value": value},
        )