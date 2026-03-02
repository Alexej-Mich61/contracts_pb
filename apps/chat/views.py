# apps/chat/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, View
from django.views.generic.detail import DetailView
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Prefetch, Exists, OuterRef
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Dialogue, Message, UserChatSettings, UserOnlineStatus
from .services import DialogueService, OnlineStatusService

User = get_user_model()


class ChatView(LoginRequiredMixin, TemplateView):
    """Главная страница чата со списком пользователей."""
    template_name = "chat/chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Получаем или создаем настройки пользователя
        settings, _ = UserChatSettings.objects.get_or_create(user=user)
        context["user_settings"] = settings

        # Обновляем статус онлайн текущего пользователя
        OnlineStatusService.ping(user)

        # Получаем список пользователей с диалогами и статусами
        users_data = self._get_users_list(user)
        context["users_list"] = users_data

        # Общее количество непрочитанных
        context["total_unread"] = DialogueService.get_total_unread_count(user)

        return context

    def _get_users_list(self, user):
        """Получить список пользователей с метаданными диалогов."""
        # Все пользователи кроме себя и системных (если нужно)
        users = User.objects.filter(
            is_active=True
        ).exclude(
            id=user.id
        ).select_related(
            "online_status"
        ).annotate(
            unread_count=Count(
                "dialogues_as_1__messages",
                filter=Q(
                    dialogues_as_1__participant2=user,
                    dialogues_as_1__messages__is_read=False
                )
            ) + Count(
                "dialogues_as_2__messages",
                filter=Q(
                    dialogues_as_2__participant1=user,
                    dialogues_as_2__messages__is_read=False
                )
            )
        )

        # Добавляем информацию о диалоге
        result = []
        for other_user in users:
            dialogue = DialogueService.get_or_create_dialogue(user, other_user)
            last_message = dialogue.get_last_message()

            result.append({
                "user": other_user,
                "dialogue": dialogue,
                "unread_count": dialogue.get_unread_count(user),
                "last_message": last_message,
                "is_online": getattr(other_user.online_status, 'is_online', False),
                "last_seen": getattr(other_user.online_status, 'last_seen', None),
            })

        # Сортируем: сначала с непрочитанными, потом по времени последнего сообщения
        result.sort(
            key=lambda x: (-x["unread_count"], x["last_message"].created_at if x["last_message"] else timezone.now()),
            reverse=True)

        return result


class DialogueView(LoginRequiredMixin, DetailView):
    """Страница конкретного диалога."""
    model = Dialogue
    template_name = "chat/dialogue.html"
    context_object_name = "dialogue"
    pk_url_kwarg = "dialogue_id"

    def get_queryset(self):
        # Только диалоги, где участвует текущий пользователь
        user = self.request.user
        return Dialogue.objects.filter(
            Q(participant1=user) | Q(participant2=user)
        ).prefetch_related(
            "messages__sender"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dialogue = self.object
        user = self.request.user

        # Отмечаем сообщения как прочитанные
        dialogue.mark_as_read(user)

        # Собеседник
        context["other_user"] = dialogue.get_other_participant(user)

        # Сообщения
        context["messages"] = dialogue.messages.select_related("sender").all()

        # Настройки звука для шаблона
        settings, _ = UserChatSettings.objects.get_or_create(user=user)
        context["sound_settings"] = {
            "enabled": settings.is_sound_enabled,
            "volume": settings.volume,
            "sound_url": settings.get_sound_url(),
        }

        return context


class SendMessageView(LoginRequiredMixin, View):
    """Отправка сообщения (HTMX)."""

    def post(self, request, dialogue_id):
        dialogue = get_object_or_404(
            Dialogue,
            id=dialogue_id
        )
        user = request.user

        # Проверяем, что пользователь участвует в диалоге (исправленная проверка)
        if user.id not in [dialogue.participant1_id, dialogue.participant2_id]:
            return HttpResponse("Forbidden", status=403)

        text = request.POST.get("text", "").strip()
        if not text:
            return HttpResponse("Empty message", status=400)

        # Создаем сообщение
        message = Message.objects.create(
            dialogue=dialogue,
            sender=user,
            text=text
        )

        # Обновляем время диалога
        dialogue.save(update_fields=["updated_at"])

        # Если HTMX-запрос - возвращаем фрагмент
        if request.headers.get("HX-Request"):
            return render(request, "chat/partials/message.html", {
                "message": message,
                "current_user": user  # Передаем current_user вместо is_me
            })

        return redirect("chat:dialogue", dialogue_id=dialogue.id)


class LoadMessagesView(LoginRequiredMixin, View):
    """Загрузка новых сообщений (HTMX polling)."""

    def get(self, request, dialogue_id):
        dialogue = get_object_or_404(Dialogue, id=dialogue_id)
        user = request.user

        if user not in [dialogue.participant1, dialogue.participant2]:
            return HttpResponse("Forbidden", status=403)

        # Получаем ID последнего известного сообщения (если передан)
        last_id = request.GET.get("last_id")

        messages = dialogue.messages.select_related("sender")
        if last_id:
            messages = messages.filter(id__gt=last_id)

        # Отмечаем как прочитанные
        messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

        return render(request, "chat/partials/messages_list.html", {
            "messages": messages,
            "current_user": user
        })


class UpdateSettingsView(LoginRequiredMixin, View):
    """Обновление настроек чата (HTMX)."""

    def post(self, request):
        settings, _ = UserChatSettings.objects.get_or_create(user=request.user)

        # Обновляем звук
        if "is_sound_enabled" in request.POST:
            settings.is_sound_enabled = request.POST.get("is_sound_enabled") == "on"

        if "volume" in request.POST:
            try:
                volume = int(request.POST.get("volume"))
                settings.volume = max(0, min(100, volume))
            except ValueError:
                pass

        settings.save()

        if request.headers.get("HX-Request"):
            return render(request, "chat/partials/settings_form.html", {
                "settings": settings
            })

        return redirect("chat:chat")


class UserListPartialView(LoginRequiredMixin, View):
    """Частичное обновление списка пользователей (для polling)."""

    def get(self, request):
        # Обновляем свой статус
        OnlineStatusService.ping(request.user)

        # Получаем обновленный список
        chat_view = ChatView()
        chat_view.request = request
        users_data = chat_view._get_users_list(request.user)

        return render(request, "chat/partials/user_list.html", {
            "users_list": users_data
        })


class PingOnlineView(LoginRequiredMixin, View):
    """Ping для обновления статуса онлайн."""

    def post(self, request):
        OnlineStatusService.ping(request.user)
        return JsonResponse({"status": "ok"})