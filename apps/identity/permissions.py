# apps/identity/permissions.py
from django.core.exceptions import PermissionDenied
from apps.identity.models import Employee


class ContractPermission:
    """
    Все проверки в одном месте.
    Используем во вьюшках и в шаблонах.
    """

    def __init__(self, user, company):
        self.user = user
        try:
            self.emp = Employee.objects.get(user=user, company=company, is_active=True)
        except Employee.DoesNotExist:
            self.emp = None

    # базовые роли
    def is_admin(self) -> bool:
        return self.emp is not None and self.emp.is_admin()

    def is_manager(self) -> bool:
        return self.emp is not None and self.emp.is_manager()

    def is_employee(self) -> bool:
        return self.emp is not None and self.emp.is_employee()

    # конкретные пермиссии
    def can_delete(self) -> bool:
        return self.is_admin() or (self.is_manager() and self.emp.can_delete_contract)

    def can_edit_systems(self) -> bool:
        return self.is_admin() or (self.is_manager() and self.emp.can_edit_systems)

    def can_edit_sign_stage(self) -> bool:
        return self.is_admin() or (self.is_manager() and self.emp.can_edit_sign_stage)

    def can_edit_full(self) -> bool:
        """Может ли редактировать ВСЕ поля договора."""
        return self.is_admin()

    def can_view(self) -> bool:
        """Может ли вообще видеть договоры этой компании."""
        return self.emp is not None