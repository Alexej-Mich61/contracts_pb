# apps/contract_core/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
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
    Work,
    SystemType,
    SigningStage,
)
from .forms import (
    AkForm,
    CompanyForm,
    ContractForm,
    ContractSigningStageForm,
    ProtectionObjectFormSet,
    InterimActFormSet,
    FinalActForm,
)
from .services.history_service import ContractHistoryService
from apps.contract_core.services.signing_stage_report_service import (
    SigningStageReportService,
)

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
        # from auditlog.models import LogEntry
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

    def _has_active_filters(self):
        """Проверяет, есть ли активные фильтры в GET-параметрах."""
        # Игнорируем служебные параметры и location=active (дефолт)
        ignored = {'page', 'csrfmiddlewaretoken', 'hx-request', 'hx-target', 'hx-current-url'}

        # Для отладки — выводим все параметры
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"GET params: {dict(self.request.GET)}")

        for key, value in self.request.GET.items():
            if key in ignored:
                continue
            # location=active считается дефолтным, не фильтром
            if key == 'location' and value == 'active':
                logger.info(f"Skipping default location=active")
                continue
            # Любое непустое значение — это фильтр
            if value and str(value).strip():
                logger.info(f"Found filter: {key}={value}")
                return True

        logger.info("No active filters found")
        return False

    def get_queryset(self):
        base_queryset = Contract.objects.for_user(self.request.user)
        service = ContractFilterService(self.request, queryset=base_queryset)
        filtered = service.filter()

        # Если нет фильтров — ограничиваем 10 последними
        has_filters = self._has_active_filters()
        self._has_filters = has_filters  # сохраняем для использования в контексте

        if not has_filters:
            return filtered[:10]

        return filtered

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_data'] = ContractFilterService.get_filter_choices()

        region_id = self.request.GET.get('region')
        context['districts'] = ContractFilterService.get_districts_by_region(region_id)

        # Используем сохранённое значение или пересчитываем
        has_filters = getattr(self, '_has_filters', self._has_active_filters())
        context['is_limited'] = not has_filters

        return context


class ContractListHtmxView(LoginRequiredMixin, ListView):
    """HTMX эндпоинт для фильтрованного списка договоров"""
    model = Contract
    template_name = "contracts/partials/contract_list_content.html"
    context_object_name = "contracts"
    paginate_by = 10

    def _has_active_filters(self):
        """Проверяет, есть ли активные фильтры в GET-параметрах."""
        ignored = {'page', 'csrfmiddlewaretoken', 'hx-request', 'hx-target', 'hx-current-url'}

        for key, value in self.request.GET.items():
            if key in ignored:
                continue
            if key == 'location' and value == 'active':
                continue
            if value and str(value).strip():
                return True
        return False

    def get_queryset(self):
        base_queryset = Contract.objects.for_user(self.request.user)
        service = ContractFilterService(self.request, queryset=base_queryset)
        return service.filter()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        context['is_limited'] = not self._has_active_filters()  # добавляем для HTMX
        context['request'] = self.request  # для построения URL в шаблоне
        return context


# ========== CRUD ПРЕДСТАВЛЕНИЯ ==========

class ContractCreateUpdateMixin:
    """Миксин для создания и редактирования договора с inline formsets"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context['protection_object_formset'] = ProtectionObjectFormSet(
                self.request.POST, instance=self.object
            )
            context['signing_stage_form'] = ContractSigningStageForm(
                self.request.POST,
                instance=self.object.signing_stage if self.object and hasattr(self.object, 'signing_stage') else None
            )
            if self.object:
                context['interim_act_formset'] = InterimActFormSet(
                    self.request.POST, self.request.FILES, instance=self.object
                )
                context['final_act_form'] = FinalActForm(
                    self.request.POST, self.request.FILES,
                    instance=self.object.final_act if hasattr(self.object, 'final_act') else None
                )
        else:
            context['protection_object_formset'] = ProtectionObjectFormSet(
                instance=self.object
            )

            # Стадия подписания - и при создании, и при редактировании
            if self.object and hasattr(self.object, 'signing_stage'):
                context['signing_stage_form'] = ContractSigningStageForm(
                    instance=self.object.signing_stage
                )
            else:
                # При создании - начальная стадия (первая в справочнике)
                initial_stage = SigningStage.objects.order_by('order').first()
                context['signing_stage_form'] = ContractSigningStageForm(
                    initial={'stage': initial_stage.id if initial_stage else None}
                )

            if self.object:
                context['interim_act_formset'] = InterimActFormSet(instance=self.object)

                try:
                    context['final_act_form'] = FinalActForm(instance=self.object.final_act)
                except FinalAct.DoesNotExist:
                    context['final_act_form'] = FinalActForm()

                # Отметки по системам
                context['system_checks'] = self.get_system_checks()
            else:
                context['interim_act_formset'] = InterimActFormSet()
                context['final_act_form'] = FinalActForm()

        return context

    def get_system_checks(self):
        """Получить или создать отметки по системам для договора"""
        systems = SystemType.objects.filter(is_active=True)
        checks = []
        for system in systems:
            check, created = ContractSystemCheck.objects.get_or_create(
                contract=self.object,
                system_type=system,
                defaults={'last_checked': None, 'checked_by': None}
            )
            checks.append(check)
        return checks

    def form_valid(self, form):
        context = self.get_context_data()
        protection_formset = context['protection_object_formset']
        signing_form = context['signing_stage_form']

        is_valid = True

        if not protection_formset.is_valid():
            is_valid = False

        if not signing_form.is_valid():
            is_valid = False

        if self.object:
            interim_formset = context.get('interim_act_formset')
            final_act_form = context.get('final_act_form')

            if interim_formset and not interim_formset.is_valid():
                is_valid = False
            if final_act_form and not final_act_form.is_valid():
                is_valid = False

        if not is_valid:
            return self.render_to_response(self.get_context_data(form=form))

        self.object = form.save()

        # Сохраняем formset объектов защиты
        protection_formset.instance = self.object
        protection_formset.save()

        # Сохраняем стадию подписания
        signing_stage = signing_form.save(commit=False)
        signing_stage.contract = self.object
        signing_stage.save()

        # Сохраняем акты (только при редактировании)
        if self.object and self.object.pk:
            if interim_formset:
                interim_formset.instance = self.object
                interim_formset.save()
            if final_act_form:
                final_act = final_act_form.save(commit=False)
                final_act.contract = self.object
                if final_act_form.cleaned_data.get('present') and not final_act.checked_by:
                    final_act.checked_by = self.request.user
                    final_act.checked_at = timezone.now()
                final_act.save()

        return redirect(self.get_success_url())


class ContractCreateView(LoginRequiredMixin, ContractCreateUpdateMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Договор успешно создан")
        return reverse_lazy('contract_core:contract_update', kwargs={'pk': self.object.pk})


class ContractUpdateView(LoginRequiredMixin, ContractAccessMixin, ContractCreateUpdateMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"
    pk_url_kwarg = 'pk'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Договор успешно обновлён")
        return reverse_lazy('contract_core:contract_list')


class MarkSystemCheckView(LoginRequiredMixin, View):
    """Отметить проверку системы (с текущей датой и пользователем)"""

    def post(self, request, contract_pk, system_type_pk):
        contract = get_object_or_404(Contract, pk=contract_pk)
        system_type = get_object_or_404(SystemType, pk=system_type_pk)

        check, created = ContractSystemCheck.objects.get_or_create(
            contract=contract,
            system_type=system_type
        )

        check.last_checked = timezone.now().date()
        check.checked_by = request.user
        check.note = request.POST.get('note', '')[:200]
        check.save()

        messages.success(request, f"Отмечено: {system_type.name}")
        return redirect('contract_core:contract_update', pk=contract_pk)


class AddAkToObjectView(LoginRequiredMixin, View):
    """Привязать АК к объекту защиты"""

    def post(self, request, contract_pk, object_pk, ak_pk):
        contract = get_object_or_404(Contract, pk=contract_pk)
        protection_object = get_object_or_404(ProtectionObject, pk=object_pk, contract=contract)
        ak = get_object_or_404(Ak, pk=ak_pk)

        protection_object.aks.add(ak)

        # Возвращаем обновленный список АК для HTMX
        return render(request, 'contracts/partials/contract_form_attached_aks.html', {
            'object': protection_object,
            'contract': contract
        })


class RemoveAkFromObjectView(LoginRequiredMixin, View):
    """Отвязать АК от объекта защиты"""

    def delete(self, request, contract_pk, object_pk, ak_pk):
        contract = get_object_or_404(Contract, pk=contract_pk)
        protection_object = get_object_or_404(ProtectionObject, pk=object_pk, contract=contract)
        ak = get_object_or_404(Ak, pk=ak_pk)

        protection_object.aks.remove(ak)

        return render(request, 'contracts/partials/contract_form_attached_aks.html', {
            'object': protection_object,
            'contract': contract
        })





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


class FilterExecutorsView(LoginRequiredMixin, View):
    """HTMX: получить исполнителей по типу договора"""

    def get(self, request):
        contract_type = request.GET.get('type')
        user = request.user

        user_companies = Company.objects.filter(
            employees__user=user,
            employees__is_active=True
        ).values_list('id', flat=True)

        type_filter = Q()
        if contract_type in ['oneoff_licensee', 'longterm_to_licensee']:
            type_filter |= Q(is_licensee=True)
        if contract_type == 'oneoff_lab':
            type_filter |= Q(is_laboratory=True)

        executors = Company.objects.filter(
            (Q(id__in=user_companies) | type_filter) &
            (Q(is_licensee=True) | Q(is_laboratory=True))
        ).distinct().order_by('name')

        selected = request.GET.get('executor', '')

        return render(request, 'contracts/partials/contract_form_executor_select.html', {
            'executors': executors,
            'selected': selected,
        })


class FilterWorksView(LoginRequiredMixin, View):
    """HTMX: получить работы по типу договора"""

    def get(self, request):
        contract_type = request.GET.get('type')

        work_type_map = {
            'oneoff_licensee': 'work_oneoff_licensee',
            'longterm_to_licensee': 'work_longterm_to_licensee',
            'oneoff_lab': 'work_oneoff_lab',
        }

        works = Work.objects.none()
        if contract_type in work_type_map:
            works = Work.objects.filter(
                work_type=work_type_map[contract_type],
                is_active=True
            )

        selected = request.GET.get('work', '')

        return render(request, 'contracts/partials/contract_form_work_select.html', {
            'works': works,
            'selected': selected,
        })


class CustomerSearchView(LoginRequiredMixin, View):
    """HTMX: поиск заказчика по названию или ИНН"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        customers = []

        if len(query) >= 2:
            customers = Company.objects.filter(
                is_customer=True
            ).filter(
                Q(name__icontains=query) | Q(inn__icontains=query)
            )[:10]

        return render(request, 'contracts/partials/contract_form_customer_search_results.html', {
            'customers': customers,
            'query': query,
        })


class FilterDistrictsByRegionView(LoginRequiredMixin, View):
    """HTMX: получить районы по выбранному региону (для объекта защиты)"""

    def get(self, request):
        region_id = request.GET.get('region')
        districts = District.objects.none()

        if region_id:
            districts = District.objects.filter(region_id=region_id).order_by('name')

        selected = request.GET.get('district', '')

        return render(request, 'contracts/partials/contract_form_district_field.html', {
            'districts': districts,
            'selected': selected,
        })


class AkSearchView(LoginRequiredMixin, View):
    """HTMX: поиск АК по ID, номеру или названию"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        protection_object_id = request.GET.get('protection_object')

        aks = []
        if len(query) >= 2:
            q_filter = Q(name__icontains=query)
            if query.isdigit():
                q_filter |= Q(number=query) | Q(id=query)

            aks = Ak.objects.filter(q_filter)[:10]

        attached_aks = []
        if protection_object_id and protection_object_id != 'new':
            attached_aks = Ak.objects.filter(
                protection_objects__id=protection_object_id
            ).values_list('id', flat=True)

        return render(request, 'contracts/partials/contract_form_ak_search_results.html', {
            'aks': aks,
            'attached_ids': list(attached_aks),
        })


class DynamicFieldsView(LoginRequiredMixin, View):
    """HTMX: обновление всех динамических полей при смене типа договора"""

    def get(self, request):
        contract_type = request.GET.get('type')

        form = ContractForm(
            data={'type': contract_type} if contract_type else {},
            user=request.user
        )

        return render(request, 'contracts/partials/contract_form_dynamic_fields.html', {
            'form': form,
            'contract_type': contract_type,
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

# отчет по стадиям подписания
class ContractSigningStageReportsView(LoginRequiredMixin, TemplateView):
    """
    View для отображения отчёта по стадиям подписания договоров.

    Ответственность:
    - Аутентификация/авторизация (через LoginRequiredMixin)
    - Делегирование сбора данных сервису
    - Подготовка контекста для шаблона
    """
    template_name = "reports/contract_signing_stage_reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Делегируем бизнес-логику сервису
        service = SigningStageReportService()
        report_data = service.get_report_data(self.request.user)

        context['report_data'] = report_data
        context['signing_stages'] = service.get_all_stages()

        return context

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