# apps/identity/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name = "identity"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("login/", auth_views.LoginView.as_view(
        template_name="authorization.html",
        next_page="identity:home"
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(
        next_page="identity:login"
    ), name="logout"),
    path("catalogs/users/", views.UsersListView.as_view(), name="users_list"),
]
