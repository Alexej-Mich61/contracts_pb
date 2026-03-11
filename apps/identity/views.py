# apps/identity/views.py
from django.shortcuts import render
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Prefetch

from .models import User, Employee


# Create your views here.

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"


class UsersListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "catalogs/users_list.html"
    context_object_name = "users"

    def get_queryset(self):
        return User.objects.prefetch_related(
            Prefetch('employments', queryset=Employee.objects.select_related('company')),
            'manager_permissions',
        ).order_by('last_name', 'first_name')


class FAQView(LoginRequiredMixin, TemplateView):
    template_name = "FAQ.html"


