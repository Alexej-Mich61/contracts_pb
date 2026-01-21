# # apps/identity/views.py
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from apps.contract_core.models import Ak
from apps.companies.models import Company
from .models import User

# Create your views here.

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

class ContractOneoffLicenseeView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_oneoff_licensee.html"

class ContractLongtermToLicenseeView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_longterm_to_licensee.html"

class ContractOneoffLabView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_oneoff_lab.html"

class ContractHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_history.html"

class ContractTrashView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_trash.html"

class CustomerReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/customer_repots.html"

class ExecutorReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/executor_reports.html"

class SubcontractorsReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/subcontractors_reports.html"

class AkListView(LoginRequiredMixin, ListView):
    model = Ak
    template_name = "catalogs/ak_list.html"
    context_object_name = "aks"

class AkCreateView(LoginRequiredMixin, CreateView):
    model = Ak
    template_name = "catalogs/ak_form.html"
    fields = ['number', 'name', 'address', 'region', 'district']
    success_url = reverse_lazy('identity:ak_list')

    def form_valid(self, form):
        messages.success(self.request, "АК успешно добавлен.")
        return super().form_valid(form)

class CompaniesListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "catalogs/companies_list.html"
    context_object_name = "companies"

class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    template_name = "catalogs/company_form.html"
    fields = ['name', 'inn', 'fias_code', 'is_customer', 'is_licensee', 'is_lab', 'is_subcontractor']
    success_url = reverse_lazy('identity:companies_list')

    def form_valid(self, form):
        messages.success(self.request, "Компания успешно добавлена.")
        return super().form_valid(form)

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

class ChatView(LoginRequiredMixin, TemplateView):
    template_name = "chat/chat.html"

class FAQView(LoginRequiredMixin, TemplateView):
    template_name = "FAQ.html"
