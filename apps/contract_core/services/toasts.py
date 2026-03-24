# apps/contract_core/services/toasts.py
"""
Упрощенный сервис HTMX-тостов.
Только два типа: success (успешно сохранено) и error (ошибка сохранения).
"""

import uuid
import json
from typing import Optional
from django.http import HttpResponse
from django.template.loader import render_to_string


class ToastService:
    DEFAULT_DURATION = 2000  # 5 секунд

    def __init__(self, is_success: bool = True, duration: Optional[int] = None):
        self.is_success = is_success
        self.duration = duration or self.DEFAULT_DURATION
        self.toast_id = f"toast-{str(uuid.uuid4())[:8]}"

    def render(self) -> str:
        template = 'partials/toast_success.html' if self.is_success else 'partials/toast_error.html'
        context = {
            'message': 'Успешное сохранение' if self.is_success else 'Ошибка сохранения данных',
            'toast_id': self.toast_id,
            'duration': self.duration,
        }
        return render_to_string(template, context)

    def to_oob_swap(self) -> str:
        """Теперь добавляем тост в конец контейнера, а не заменяем его полностью"""
        toast_html = self.render()
        return f'<div hx-swap-oob="beforeend:#toast-container">{toast_html}</div>'


class ToastResponse(HttpResponse):
    def __init__(
        self,
        is_success: bool = True,
        *,
        refresh_url: Optional[str] = None,
        close_modal: bool = True,
        duration: Optional[int] = None,
        **kwargs,
    ):
        toast = ToastService(is_success=is_success, duration=duration)
        content = self._build_content(toast, close_modal, refresh_url)
        super().__init__(content=content, content_type='text/html', **kwargs)

        # Полезный триггер (можно слушать в custom.js если нужно)
        self['HX-Trigger'] = json.dumps({'toastShown': {'success': is_success}})

    def _build_content(
        self, toast: ToastService, close_modal: bool, refresh_url: Optional[str]
    ) -> str:
        parts = [toast.to_oob_swap()]

        scripts = []

        if close_modal:
            scripts.append(
                'var modalEl = document.getElementById("companyModal");'
                'if (modalEl) {'
                '  var modal = bootstrap.Modal.getInstance(modalEl);'
                '  if (modal) modal.hide();'
                '}'
            )

        # ←←← ГЛАВНОЕ ИСПРАВЛЕНИЕ ←←←
        if refresh_url:
            # Ждём ровно столько же, сколько живёт тост + небольшой запас на fade-out
            delay = toast.duration + 600
            scripts.append(
                f'setTimeout(() => {{'
                f'  htmx.ajax("GET", "{refresh_url}", {{target: "body", swap: "outerHTML"}});'
                f'}}, {delay});'
            )

        if scripts:
            parts.append(f'<script>{" ".join(scripts)}</script>')

        return '\n'.join(parts)


# Удобные функции (оставил те же сигнатуры)
def toast_ok(
    refresh_url: Optional[str] = None,
    close_modal: bool = True,
    duration: Optional[int] = None,
) -> ToastResponse:
    return ToastResponse(
        is_success=True,
        refresh_url=refresh_url,
        close_modal=close_modal,
        duration=duration,
    )


def toast_fail(
    close_modal: bool = False,
    duration: Optional[int] = None,
) -> ToastResponse:
    return ToastResponse(
        is_success=False,
        refresh_url=None,
        close_modal=close_modal,
        duration=duration,
    )