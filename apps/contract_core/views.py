# apps/contract_core/views.py
import logging
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView
from django.db.models import Q
from django.db.models import Count
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.views.generic.base import View

from .models import (
    Ak,
    Company,
    Contract,
    ProtectionObject,
    FinalAct,
    Region,
    District,
    InterimAct,
    ContractSigningStage,
    ContractSystemCheck,
    )
from .forms import AkForm, CompanyForm, ContractForm



# Create your views here.

# auditlog
class ContractHistoryView(LoginRequiredMixin, ListView):
    model = LogEntry
    template_name = "contracts/contract_history.html"
    context_object_name = "logs"
    paginate_by = 20

    def get_queryset(self):
        contract_pk = self.kwargs['pk']
        self.contract = get_object_or_404(Contract, pk=contract_pk)

        # Получаем ContentType для всех моделей
        content_types = ContentType.objects.get_for_models(
            Contract, FinalAct, InterimAct, ContractSigningStage,
            ContractSystemCheck, ProtectionObject, Ak
        )

        # Начинаем с Q-объекта для самого Contract
        q_objects = Q(
            content_type=content_types[Contract],
            object_id=str(contract_pk)
        )

        # Собираем ID связанных объектов и добавляем в фильтр

        # 1. FinalAct (OneToOne)
        try:
            final_act = FinalAct.objects.get(contract_id=contract_pk)
            q_objects |= Q(
                content_type=content_types[FinalAct],
                object_id=str(final_act.pk)
            )
        except FinalAct.DoesNotExist:
            pass

        # 2. InterimAct (ForeignKey)
        interim_ids = InterimAct.objects.filter(
            contract_id=contract_pk
        ).values_list('id', flat=True)
        if interim_ids:
            q_objects |= Q(
                content_type=content_types[InterimAct],
                object_id__in=[str(i) for i in interim_ids]
            )

        # 3. ContractSigningStage (OneToOne)
        try:
            signing_stage = ContractSigningStage.objects.get(contract_id=contract_pk)
            q_objects |= Q(
                content_type=content_types[ContractSigningStage],
                object_id=str(signing_stage.pk)
            )
        except ContractSigningStage.DoesNotExist:
            pass

        # 4. ContractSystemCheck (ForeignKey)
        system_check_ids = ContractSystemCheck.objects.filter(
            contract_id=contract_pk
        ).values_list('id', flat=True)
        if system_check_ids:
            q_objects |= Q(
                content_type=content_types[ContractSystemCheck],
                object_id__in=[str(i) for i in system_check_ids]
            )

        # 5. ProtectionObject (ForeignKey)
        protection_ids = ProtectionObject.objects.filter(
            contract_id=contract_pk
        ).values_list('id', flat=True)
        protection_ids_list = list(protection_ids)

        if protection_ids_list:
            q_objects |= Q(
                content_type=content_types[ProtectionObject],
                object_id__in=[str(i) for i in protection_ids_list]
            )

            # 6. Ak — связан через ProtectionObject (ManyToMany)
            ak_ids = Ak.objects.filter(
                protection_objects__id__in=protection_ids_list
            ).values_list('id', flat=True).distinct()

            if ak_ids:
                q_objects |= Q(
                    content_type=content_types[Ak],
                    object_id__in=[str(i) for i in ak_ids]
                )

        return LogEntry.objects.filter(q_objects).select_related(
            'actor', 'content_type'
        ).order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contract'] = self.contract
        return context


class ContractListView(LoginRequiredMixin, ListView):
    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset().filter(
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

        # Фильтр по типу (если передан в GET)
        contract_type = self.request.GET.get('type')
        if contract_type:
            qs = qs.filter(type=contract_type)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        context['current_type'] = self.request.GET.get('type', 'all')
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

    def get_success_url(self):
        return reverse_lazy('contract_core:contract_list')

    def form_valid(self, form):
        messages.success(self.request, "Договор успешно создан")
        return super().form_valid(form)


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_success_url(self):
        return reverse_lazy('contract_core:contract_list')

    def form_valid(self, form):
        messages.success(self.request, "Договор успешно обновлён")
        return super().form_valid(form)




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


# Справочник AK
class AkListView(LoginRequiredMixin, ListView):
    model = Ak
    template_name = "catalogs/ak_list.html"
    context_object_name = "aks"
    paginate_by = 25
    ordering = ['-id']

    def get_queryset(self):
        qs = Ak.objects.all().select_related('district__region').order_by('-id')

        # Поиск по ID
        id_search = self.request.GET.get('id', '').strip()
        if id_search and id_search.isdigit():
            qs = qs.filter(id=int(id_search))

        # Поиск по номеру АК
        number_search = self.request.GET.get('number', '').strip()
        if number_search and number_search.isdigit():
            qs = qs.filter(number=int(number_search))

        # Поиск по названию
        name_search = self.request.GET.get('name', '').strip()
        if name_search:
            qs = qs.filter(name__icontains=name_search)

        # Поиск по адресу
        address_search = self.request.GET.get('address', '').strip()
        if address_search:
            qs = qs.filter(address__icontains=address_search)

        # Фильтр по региону
        region_id = self.request.GET.get('region', '').strip()
        if region_id and region_id.isdigit():
            qs = qs.filter(district__region_id=int(region_id))

        # Фильтр по району (только если выбран регион)
        district_id = self.request.GET.get('district', '').strip()
        if district_id and district_id.isdigit():
            qs = qs.filter(district_id=int(district_id))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Все регионы для выпадающего списка
        context['regions'] = Region.objects.all().order_by('name')

        # Районы для выбранного региона (или все, если регион не выбран)
        region_id = self.request.GET.get('region', '').strip()
        if region_id and region_id.isdigit():
            context['districts'] = District.objects.filter(region_id=int(region_id)).order_by('name')
        else:
            context['districts'] = District.objects.none()

        # Сохраняем выбранные значения для формы
        context['selected_region'] = region_id
        context['selected_district'] = self.request.GET.get('district', '')
        context['search_id'] = self.request.GET.get('id', '')
        context['search_number'] = self.request.GET.get('number', '')
        context['search_name'] = self.request.GET.get('name', '')
        context['search_address'] = self.request.GET.get('address', '')

        return context


class AkCreateView(LoginRequiredMixin, CreateView):
    model = Ak
    form_class = AkForm
    template_name = "catalogs/partials/ak_form_modal.html"
    success_url = reverse_lazy('contract_core:ak_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = "Добавить АК"
        return context

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "АК успешно добавлен!")

        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                '<script>window.location.reload()</script>',
                headers={'HX-Trigger': 'akSaved'}
            )
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class AkUpdateView(LoginRequiredMixin, UpdateView):
    model = Ak
    form_class = AkForm
    template_name = "catalogs/partials/ak_form_modal.html"
    success_url = reverse_lazy('contract_core:ak_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = f"Редактировать АК №{self.object.number}"
        return context

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "АК успешно обновлён!")

        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                '<script>window.location.reload()</script>',
                headers={'HX-Trigger': 'akSaved'}
            )
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))




# Вьюхи для Справочника компаний

class CompaniesListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "catalogs/companies_list.html"
    context_object_name = "companies"
    paginate_by = 30
    ordering = ['-id']

    def get_paginate_by(self, queryset):
        # Если есть любой фильтр — убираем лимит в 10 записей
        if self.request.GET.get('q') or self.request.GET.get('id') or self.request.GET.getlist('role'):
            return self.paginate_by
        # По умолчанию — только 10 последних
        return 10

    def get_queryset(self):
        # Сначала получаем базовый queryset
        qs = Company.objects.all().order_by('-id')

        # Проверяем, есть ли активные фильтры
        has_filters = (
                self.request.GET.get('q') or
                self.request.GET.get('id') or
                self.request.GET.getlist('role')
        )

        # Применяем фильтры (до distinct и среза!)
        id_search = self.request.GET.get('id', '').strip()
        if id_search and id_search.isdigit():
            qs = qs.filter(id=int(id_search))

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(inn__icontains=q) | Q(name__icontains=q))

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

        # Теперь distinct (до среза!)
        qs = qs.distinct()

        # И только потом срез, если нужно
        if not has_filters:
            qs = qs[:10]

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_roles'] = self.request.GET.getlist('role')
        # Флаг для шаблона — показывать ли сообщение о лимите
        context['is_limited'] = not (
                self.request.GET.get('q') or
                self.request.GET.get('id') or
                self.request.GET.getlist('role')
        )
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