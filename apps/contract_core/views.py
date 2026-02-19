# apps/contract_core/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView
from django.db.models import Q
from django.db.models import Count

from .models import Ak, Company, Contract
from .models import Contract, ProtectionObject, Ak, FinalAct, InterimAct
from .forms import ContractForm  # создадим ниже
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


class OneoffLicenseeListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = "contracts/contract_oneoff_licensee.html"
    context_object_name = "contracts"
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        return super().get_queryset().filter(
            type=Contract.Type.ONEOFF_LICENSEE,
            is_trash=False,
            is_archived=False
        ).select_related(
            'customer', 'executor', 'work'
        ).prefetch_related(
            'objects__district__region',
            'objects__subcontractor',
            'objects__aks',
            'final_act',
            'interim_acts',
            'signing_stage',
            'system_checks__system_type'
        ).annotate(
            object_count=Count('objects'),
            ak_count=Count('objects__aks')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        return context


class ContractDetailView(LoginRequiredMixin, DetailView):
    model = Contract
    template_name = "contracts/contract_detail.html"
    context_object_name = "contract"

    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer', 'executor', 'work'
        ).prefetch_related(
            'objects__district__region',
            'objects__subcontractor',
            'objects__aks',
            'final_act',
            'interim_acts',
            'signing_stage',
            'system_checks__system_type'
        )


class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy('contract_core:contract_oneoff_licensee')

    def form_valid(self, form):
        messages.success(self.request, "Договор успешно создан")
        return super().form_valid(form)


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    success_url = reverse_lazy('contract_core:contract_oneoff_licensee')

    def form_valid(self, form):
        messages.success(self.request, "Договор успешно обновлён")
        return super().form_valid(form)


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


# История договоров
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
    form_class = AkForm
    template_name = "catalogs/ak_form.html"
    success_url = reverse_lazy('contract_core:ak_list')

    def form_valid(self, form):
        messages.success(self.request, "АК успешно добавлен.")
        return super().form_valid(form)




# Вьюхи для Справочника компаний

class CompaniesListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "catalogs/companies_list.html"
    context_object_name = "companies"
    paginate_by = 30
    ordering = ['-id']  # или ['-pk']

    def get_queryset(self):
        qs = super().get_queryset()

        # Поиск
        q = self.request.GET.get('q', '').strip()
        if q:
            # Проверяем, является ли поиск числом (ID)
            if q.isdigit():
                qs = qs.filter(Q(id=q) | Q(inn__icontains=q) | Q(name__icontains=q))
            else:
                qs = qs.filter(Q(inn__icontains=q) | Q(name__icontains=q))

        # Фильтр по ролям
        roles = self.request.GET.getlist('role')
        if roles:
            role_filters = Q()
            if 'customer' in roles:
                role_filters |= Q(is_customer=True)
            if 'licensee' in roles:
                role_filters |= Q(is_licensee=True)
            if 'laboratory' in roles:
                role_filters |= Q(is_laboratory=True)
            if 'subcontractor' in roles:
                role_filters |= Q(is_subcontractor=True)
            qs = qs.filter(role_filters)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_roles'] = self.request.GET.getlist('role')
        return context



# c HTMX
class CompanyCreateView(LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = "catalogs/partials/company_form_modal.html"
    success_url = reverse_lazy('contract_core:companies_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = "Добавить компанию"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Компания успешно добавлена!")

        if self.request.headers.get('HX-Request'):
            # HTMX запрос — закрываем модалку и обновляем страницу
            return HttpResponse(
                '<script>window.location.reload()</script>',
                headers={'HX-Trigger': 'companySaved'}
            )
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        # Возвращаем форму с ошибками обратно в модалку
        return self.render_to_response(self.get_context_data(form=form))



# c HTMX
class CompanyUpdateView(LoginRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = "catalogs/partials/company_form_modal.html"
    success_url = reverse_lazy('contract_core:companies_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = f"Редактировать компанию: {self.object.name}"
        return context

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Компания успешно обновлена!")

        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                '<script>window.location.reload()</script>',
                headers={'HX-Trigger': 'companySaved'}
            )
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))