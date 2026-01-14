# apps/contract_core/managers.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ContractQuerySet(models.QuerySet):
    def for_user(self, user: User):
        """Оставляем только договоры компаний, в которых пользователь – активный сотрудник."""
        if user.is_superuser:
            return self
        company_ids = user.employees.filter(is_active=True).values_list("company_id", flat=True)
        return self.filter(executor_id__in=company_ids)


class ContractManager(models.Manager):
    def get_queryset(self):
        return ContractQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)