# apps/identity/mixins.py
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.urls import reverse_lazy


class PermissionRequiredMixin(AccessMixin):
    """
    Удобный и гибкий миксин для проверки прав пользователя.
    Поддерживает как строковые имена методов, так и callable.
    Хорошо работает с HTMX.
    """
    permission = None  # Например: 'can_add_contract', 'can_manage_aks' или lambda user: user.can_xxx()

    def has_permission(self) -> bool:
        """Основной метод проверки прав"""
        if not self.request.user.is_authenticated:
            return False

        user = self.request.user

        if not self.permission:
            return True  # если permission не указан — разрешаем (для ListView и т.д.)

        # Если передан callable
        if callable(self.permission):
            return self.permission(user)

        # Если передана строка — ищем метод у пользователя
        if hasattr(user, self.permission):
            perm_method = getattr(user, self.permission)
            if callable(perm_method):
                return perm_method()
            return bool(perm_method)

        return False

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission():
            if self.raise_exception or request.headers.get('HX-Request'):
                raise PermissionDenied(self.get_permission_denied_message())

            # Для обычных запросов — стандартное поведение
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        """Для HTMX возвращаем 403 без редиректа"""
        if self.request.headers.get('HX-Request'):
            # Можно вернуть пустой ответ или сообщение
            return HttpResponse(status=403)
        return super().handle_no_permission()