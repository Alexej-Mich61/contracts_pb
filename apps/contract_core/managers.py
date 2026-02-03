# apps/contract_core/managers.py
from django.db.models import Manager


class ContractManager(Manager):
    def for_user(self, user):
        """
        Возвращает queryset договоров, которые может видеть данный пользователь.
        """
        if not user or not user.is_authenticated:
            return self.none()

        # Здесь можно получить модель User, если нужно
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if user.is_superuser or user.category == User.Category.ADMIN:
            return self.all()

        # Для всех остальных — только свои компании-исполнители
        return self.filter(
            executor__employees__user=user,
            executor__employees__is_active=True
        ).distinct()