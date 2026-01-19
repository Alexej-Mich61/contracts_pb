# apps/contract_core/services.py
from datetime import date
from typing import TYPE_CHECKING
from django.db import transaction
from .models import Contract

if TYPE_CHECKING:
    from apps.identity.models import User
    from apps.companies.models import Company

@transaction.atomic
def create_contract(
    *,
    number: str,
    type: str,
    executor: "Company",
    customer: "Company",
    total_sum: float,
    creator: "User",
) -> Contract:
    return Contract.objects.create(
        number=number,
        type=type,
        executor=executor,
        customer=customer,
        total_sum=total_sum,
        creator=creator,
    )