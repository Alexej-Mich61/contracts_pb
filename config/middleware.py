# config/middleware.py
from threading import local
import logging



logger = logging.getLogger(__name__)

_thread_locals = local()


def get_current_user():
    """Получить текущего пользователя из thread-local хранилища."""
    return getattr(_thread_locals, 'user', None)


class CurrentUserMiddleware:
    """
    Middleware, который сохраняет текущего пользователя в thread-local,
    чтобы его можно было использовать в save() моделей.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Сохраняем пользователя только если он аутентифицирован
        user = request.user if request.user.is_authenticated else None
        logger.debug(f"Current user set: {user}")
        _thread_locals.user = user

        response = self.get_response(request)

        # Очищаем после обработки запроса
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user

        return response