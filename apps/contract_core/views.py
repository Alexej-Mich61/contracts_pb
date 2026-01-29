# apps/contract_core/views.py
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import TemplateView, ListView, CreateView

from .models import Ak, Company


# Create your views here.


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
    template_name = "reports/customer_reports.html"

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
    success_url = reverse_lazy('contract_core:ak_list')

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
    success_url = reverse_lazy('contract_core:companies_list')

    def form_valid(self, form):
        messages.success(self.request, "Компания успешно добавлена.")
        return super().form_valid(form)

