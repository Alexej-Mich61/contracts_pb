# apps/contract_core/views.py
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import TemplateView, ListView, CreateView
from django.db.models import Q

from .models import Ak, Company, Contract
from .forms import AkForm, CompanyForm


# Create your views here.

# Базовый класс для страниц с типами договоров
class ContractTypeView(LoginRequiredMixin, TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        type_slug = self.kwargs.get('type_slug', '')
        type_display = {
            'oneoff-licensee': 'Разовый (лицензиат)',
            'longterm-licensee': 'Долгосрочный ТО (лицензиат)',
            'oneoff-lab': 'Разовый (лаборатория)',
        }.get(type_slug, 'Неизвестный тип')
        context['contract_type'] = type_display
        context['type_slug'] = type_slug
        return context


class ContractOneoffLicenseeView(ContractTypeView):
    template_name = "contracts/contract_oneoff_licensee.html"


class ContractLongtermToLicenseeView(ContractTypeView):
    template_name = "contracts/contract_longterm_to_licensee.html"


class ContractOneoffLabView(ContractTypeView):
    template_name = "contracts/contract_oneoff_lab.html"


# Универсальный список договоров с фильтром по типу
class ContractListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = "contracts/contract_list_all.html"
    context_object_name = "contracts"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_trash=False, is_archived=False)
        type_slug = self.kwargs.get('type_slug')
        if type_slug:
            type_map = {
                'oneoff-licensee': self.model.Type.ONEOFF_LICENSEE,
                'longterm-licensee': self.model.Type.LONGTERM_TO_LICENSEE,
                'oneoff-lab': self.model.Type.ONEOFF_LAB,
            }
            qs = qs.filter(type=type_map.get(type_slug))
        return qs


# История
class ContractHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_history.html"

# Корзина договоров
class ContractTrashView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_trash.html"

# Отчеты
class CustomerReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/customer_reports.html"

class ExecutorReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/executor_reports.html"

class SubcontractorsReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/subcontractors_reports.html"


# Справочники
class AkListView(LoginRequiredMixin, ListView):
    model = Ak
    template_name = "catalogs/ak_list.html"
    context_object_name = "aks"
    paginate_by = 25
    ordering = ['-number']

    def get_queryset(self):
        return super().get_queryset().select_related('district__region')


class AkCreateView(LoginRequiredMixin, CreateView):
    model = Ak
    form_class = AkForm  # создадим ниже
    template_name = "catalogs/ak_form.html"
    success_url = reverse_lazy('contract_core:ak_list')

    def form_valid(self, form):
        messages.success(self.request, "АК успешно добавлен.")
        return super().form_valid(form)


class CompaniesListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "catalogs/companies_list.html"
    context_object_name = "companies"
    paginate_by = 30
    ordering = ['name']



class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm  # создадим ниже
    template_name = "catalogs/company_form.html"
    success_url = reverse_lazy('contract_core:companies_list')

    def form_valid(self, form):
        messages.success(self.request, "Компания успешно добавлена.")
        return super().form_valid(form)

