# apps/contract_core/services/toasts.py
"""
Универсальный сервис HTMX-тостов.
Поддерживает разные модальные окна и разные справочники.
"""

import uuid
import json
from typing import Optional
from django.http import HttpResponse
from django.template.loader import render_to_string


class ToastService:
    DEFAULT_DURATION = 2000  # 2 секунды — как ты установил

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
        """Добавляем тост в конец контейнера (поддержка нескольких тостов)"""
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
        modal_id: str = "companyModal",   # ← ключевой параметр для универсальности
        **kwargs,
    ):
        self.modal_id = modal_id
        toast = ToastService(is_success=is_success, duration=duration)
        content = self._build_content(toast, close_modal, refresh_url)
        super().__init__(content=content, content_type='text/html', **kwargs)

        # Полезный триггер (можно использовать в custom.js при необходимости)
        self['HX-Trigger'] = json.dumps({'toastShown': {'success': is_success}})

    def _build_content(
        self, toast: ToastService, close_modal: bool, refresh_url: Optional[str]
    ) -> str:
        parts = [toast.to_oob_swap()]

        scripts = []

        if close_modal:
            # Закрываем нужную модалку (у компаний — companyModal, у АК — akModal и т.д.)
            scripts.append(
                f'var modalEl = document.getElementById("{self.modal_id}");'
                f'if (modalEl) {{'
                f'  var modal = bootstrap.Modal.getInstance(modalEl);'
                f'  if (modal) modal.hide();'
                f'}}'
            )

        if refresh_url:
            # Ждём, пока тост покажется + небольшая задержка на fade-out
            delay = toast.duration + 600
            scripts.append(
                f'setTimeout(() => {{'
                f'  htmx.ajax("GET", "{refresh_url}", {{target: "body", swap: "outerHTML"}});'
                f'}}, {delay});'
            )

        if scripts:
            parts.append(f'<script>{" ".join(scripts)}</script>')

        return '\n'.join(parts)


# ==================== Удобные функции ====================

def toast_ok(
    refresh_url: Optional[str] = None,
    close_modal: bool = True,
    duration: Optional[int] = None,
    modal_id: str = "companyModal",
) -> ToastResponse:
    """Тост успеха + (опционально) обновление списка"""
    return ToastResponse(
        is_success=True,
        refresh_url=refresh_url,
        close_modal=close_modal,
        duration=duration,
        modal_id=modal_id,
    )


def toast_fail(
    close_modal: bool = False,
    duration: Optional[int] = None,
    modal_id: str = "companyModal",
) -> ToastResponse:
    """Тост ошибки (модалка обычно остаётся открытой)"""
    return ToastResponse(
        is_success=False,
        refresh_url=None,
        close_modal=close_modal,
        duration=duration,
        modal_id=modal_id,
    )