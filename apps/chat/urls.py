# apps/chat/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views


app_name = "chat"


urlpatterns = [
    path("", views.ChatView.as_view(), name="chat"),
    path("dialogue/<int:dialogue_id>/", views.DialogueView.as_view(), name="dialogue"),
    path("dialogue/<int:dialogue_id>/send/", views.SendMessageView.as_view(), name="send_message"),
    path("dialogue/<int:dialogue_id>/messages/", views.LoadMessagesView.as_view(), name="load_messages"),
    path("settings/update/", views.UpdateSettingsView.as_view(), name="update_settings"),
    path("users/partial/", views.UserListPartialView.as_view(), name="user_list_partial"),
    path("ping/", views.PingOnlineView.as_view(), name="ping"),
]