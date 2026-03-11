# apps/contract_core/managers.py
from django.db.models import Manager, Q


class ContractManager(Manager):
    def for_user(self, user):
        """
        Возвращает queryset договоров, которые может видеть данный пользователь.
        Суперюзер/админ видит все, остальные — только контракты компаний-исполнителей,
        где они являются активными сотрудниками.
        """
        if not user or not user.is_authenticated:
            return self.none()

        # Админы и суперпользователи видят всё
        if user.is_superuser or getattr(user, 'is_admin', False):
            return self.all()

        # Остальные видят только контракты компаний, где они активные сотрудники
        # Используем related_name="employees" из модели Employee (company -> employees)
        return self.filter(
            executor__employees__user=user,
            executor__employees__is_active=True
        ).distinct()