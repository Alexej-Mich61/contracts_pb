# apps/identity/views.py
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
#from apps.contract_core.models import Company
from .models import User

# Create your views here.

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"


class UsersListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "catalogs/users_list.html"
    context_object_name = "users"

class UserCreateView(LoginRequiredMixin, CreateView):
    model = User
    template_name = "catalogs/user_form.html"
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'category', 'avatar']
    success_url = reverse_lazy('identity:users_list')

    def form_valid(self, form):
        messages.success(self.request, "Пользователь успешно добавлен.")
        return super().form_valid(form)


class FAQView(LoginRequiredMixin, TemplateView):
    template_name = "FAQ.html"
