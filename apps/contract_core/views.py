# apps/contract_core/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.db.models import Count
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.views import View
from .services.contract_filter_service import ContractFilterService
from .services.company_filter_service import CompanyFilterService
from .services.ak_filter_service import AkFilterService
from .mixins import ContractAccessMixin

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
from .services.history_service import ContractHistoryService


# Create your views here.



# auditlog
# ========== HTMX ЭНДПОИНТЫ ==========

class ContractHistoryHtmxView(LoginRequiredMixin, ContractAccessMixin, DetailView):
    """HTMX эндпоинт для истории договора в модальном окне"""
    model = Contract
    template_name = "contracts/partials/contract_history_modal.html"
    context_object_name = "contract"  # изменено для совместимости с миксином
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        # Базовый queryset с проверкой доступа из миксина
        queryset = super().get_queryset()
        from auditlog.models import LogEntry
        # Возвращаем контракты (LogEntry получим отдельно)
        return queryset

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        service = ContractHistoryService(self.object)
        logs = service.get_all_logs()

        context = self.get_context_data(object=self.object)
        context['logs'] = logs
        return self.render_to_response(context)


class ContractDetailHtmxView(LoginRequiredMixin, ContractAccessMixin, DetailView):
    """HTMX эндпоинт для деталей договора в модальном окне"""
    model = Contract
    template_name = "contracts/partials/contract_detail_modal.html"
    context_object_name = "contract"
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer', 'executor', 'work'
        ).prefetch_related(
            'contract_objects__district__region',
            'contract_objects__subcontractor',
            'contract_objects__aks',
            'final_act',
            'interim_acts',
            'signing_stage',
            'system_checks__system_type'
        )


# ========== СПИСОЧНЫЕ ПРЕДСТАВЛЕНИЯ ==========

class ContractListView(LoginRequiredMixin, ListView):
    """Главная страница списка договоров с фильтром"""
    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 10

    def get_queryset(self):
        # Базовый queryset с учетом прав доступа пользователя
        base_queryset = Contract.objects.for_user(self.request.user)

        # Применяем фильтры поверх ограниченного queryset
        service = ContractFilterService(self.request, queryset=base_queryset)
        return service.filter()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_data'] = ContractFilterService.get_filter_choices()

        # Для начального состояния районов
        region_id = self.request.GET.get('region')
        context['districts'] = ContractFilterService.get_districts_by_region(region_id)

        return context


class ContractListHtmxView(LoginRequiredMixin, ListView):
    """HTMX эндпоинт для фильтрованного списка договоров"""
    model = Contract
    template_name = "contracts/partials/contract_list_content.html"
    context_object_name = "contracts"
    paginate_by = 10

    def get_queryset(self):
        # Базовый queryset с учетом прав доступа
        base_queryset = Contract.objects.for_user(self.request.user)
        service = ContractFilterService(self.request, queryset=base_queryset)
        return service.filter()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        return context


# ========== CRUD ПРЕДСТАВЛЕНИЯ ==========

class ContractCreateView(LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_success_url(self):
        return reverse_lazy('contract_core:contract_list')

    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, "Договор успешно создан")
        return super().form_valid(form)


class ContractUpdateView(LoginRequiredMixin, ContractAccessMixin, UpdateView):
    """Редактирование договора с проверкой доступа"""
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    pk_url_kwarg = 'pk'

    def get_success_url(self):
        return reverse_lazy('contract_core:contract_list')

    def form_valid(self, form):
        messages.success(self.request, "Договор успешно обновлён")
        return super().form_valid(form)


class ContractDeleteView(LoginRequiredMixin, ContractAccessMixin, DeleteView):
    """Удаление договора (перемещение в корзину) с проверкой доступа"""
    model = Contract
    template_name = "contracts/contract_confirm_delete.html"
    pk_url_kwarg = 'pk'
    success_url = reverse_lazy('contract_core:contract_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.is_trash = True
        self.object.updater = request.user
        self.object.save()
        messages.success(request, "Договор перемещён в корзину")
        return redirect(self.get_success_url())


# ========== ВСПОМОГАТЕЛЬНЫЕ ВЬЮХИ ==========

class FilterWorksView(LoginRequiredMixin, View):
    """HTMX: получить работы по типу договора"""

    def get(self, request):
        contract_type = request.GET.get('contract_type')
        works = ContractFilterService.get_works_by_contract_type(contract_type)
        selected_work = request.GET.get('work', '')

        return render(request, 'contracts/partials/work_select.html', {
            'works': works,
            'selected_work': selected_work
        })


class FilterDistrictsView(LoginRequiredMixin, View):
    """HTMX: получить районы по региону"""

    def get(self, request):
        region_id = request.GET.get('region')
        districts = ContractFilterService.get_districts_by_region(region_id)
        selected_district = request.GET.get('district', '')

        return render(request, 'contracts/partials/district_select.html', {
            'districts': districts,
            'selected_district': selected_district
        })


# ========== КОРЗИНА ==========

class ContractTrashView(LoginRequiredMixin, ListView):
    """Корзина договоров с фильтрацией по правам доступа"""
    model = Contract
    template_name = "contracts/contract_trash.html"
    context_object_name = "contracts"
    paginate_by = 10

    def get_queryset(self):
        # Только удаленные договоры пользователя
        base_queryset = Contract.objects.for_user(self.request.user)
        return base_queryset.filter(is_trash=True).order_by('-updated_at')


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

    def get_paginate_by(self, queryset):
        filter_service = AkFilterService(self.request.GET)
        if filter_service.has_active_filters():
            return self.paginate_by
        return 10

    def get_queryset(self):
        filter_service = AkFilterService(self.request.GET)
        qs = filter_service.filter()

        # Применяем срез если нет фильтров
        if not filter_service.has_active_filters():
            qs = qs[:10]

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filter_service = AkFilterService(self.request.GET)
        context.update(filter_service.get_context_data())

        # Флаг для шаблона — показывать ли сообщение о лимите
        context['is_limited'] = not filter_service.has_active_filters()

        # Все регионы для выпадающего списка
        context['regions'] = Region.objects.all().order_by('name')

        # Районы для выбранного региона
        region_id = self.request.GET.get('region', '').strip()
        if region_id and region_id.isdigit():
            context['districts'] = District.objects.filter(region_id=int(region_id)).order_by('name')
        else:
            context['districts'] = District.objects.none()

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



class AkStatsView(LoginRequiredMixin, View):
    """Возвращает статистику по АК для модального окна."""

    def get(self, request, *args, **kwargs):
        from django.db.models import Q

        # Общее количество
        total = Ak.objects.count()

        # По регионам (через district__region)
        by_region = (
            Ak.objects
            .filter(district__isnull=False)
            .values('district__region__name')
            .annotate(count=Count('id'))
            .order_by('-count', 'district__region__name')
        )

        # По районам (через district)
        by_district = (
            Ak.objects
            .filter(district__isnull=False)
            .values('district__name', 'district__region__name')
            .annotate(count=Count('id'))
            .order_by('district__region__name', 'district__name')
        )

        # Преобразуем в списки словарей для удобства шаблона
        region_list = [
            {'name': item['district__region__name'], 'count': item['count']}
            for item in by_region
        ]

        district_list = [
            {
                'name': item['district__name'],
                'region_name': item['district__region__name'],
                'count': item['count']
            }
            for item in by_district
        ]

        context = {
            'total': total,
            'by_region': region_list,
            'by_district': district_list,
        }

        return render(request, 'catalogs/partials/ak_stats_modal.html', context)


# Вьюхи для Справочника компаний

class CompaniesListView(LoginRequiredMixin, ListView):
    model = Company
    template_name = "catalogs/companies_list.html"
    context_object_name = "companies"
    paginate_by = 30
    ordering = ['-id']

    def get_paginate_by(self, queryset):
        filter_service = CompanyFilterService(self.request.GET)
        if filter_service.has_active_filters():
            return self.paginate_by
        return 10

    def get_queryset(self):
        filter_service = CompanyFilterService(self.request.GET)
        qs = filter_service.filter()

        # Применяем срез если нет фильтров
        if not filter_service.has_active_filters():
            qs = qs[:10]

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_service = CompanyFilterService(self.request.GET)
        context.update(filter_service.get_context_data())
        context['is_limited'] = not filter_service.has_active_filters()
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



class CompanyStatsView(LoginRequiredMixin, View):
    """Возвращает статистику по компаниям для модального окна."""

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Q

        stats = Company.objects.aggregate(
            total=Count('id'),
            customers=Count('id', filter=Q(is_customer=True)),
            licensees=Count('id', filter=Q(is_licensee=True)),
            laboratories=Count('id', filter=Q(is_laboratory=True)),
            subcontractors=Count('id', filter=Q(is_subcontractor=True)),
            notification_agreed=Count('id', filter=Q(notification_agreed=True)),
        )

        return render(request, 'catalogs/partials/company_stats_modal.html', stats)