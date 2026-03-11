# apps/contract_core/mixins.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404


class ContractAccessMixin:
    """
    Миксин проверяет, имеет ли пользователь доступ к контракту.
    Применяйте ко всем представлениям, работающим с одним контрактом.
    """

    def get_queryset(self):
        """Возвращает queryset с учетом прав пользователя"""
        # Получаем queryset от родительского класса (или создаем новый)
        queryset = getattr(super(), 'get_queryset', lambda: self.model.objects)()

        # Если это уже QuerySet от модели Contract
        if hasattr(queryset, 'for_user'):
            return queryset.for_user(self.request.user)

        # Если нет — берем напрямую
        return self.model.objects.for_user(self.request.user)

    def get_object(self, queryset=None):
        """Получает объект с проверкой доступа"""
        if queryset is None:
            queryset = self.get_queryset()

        # Получаем pk из URL
        pk = self.kwargs.get(self.pk_url_kwarg)

        if pk is None:
            raise AttributeError(
                f"View {self.__class__.__name__} must be called with "
                f"an object pk (expected '{self.pk_url_kwarg}' in URL)"
            )

        # get_object_or_404 с ограниченным queryset вернет 404, если нет доступа
        obj = get_object_or_404(queryset, pk=pk)
        return obj