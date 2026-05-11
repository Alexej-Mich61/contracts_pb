# apps/contract_core/views.py
from django.http import HttpResponse, HttpResponseRedirect, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.db.models import Count, Sum
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.views import View
from collections import defaultdict
from .services.contract_filter_service import ContractFilterService
from .services.company_filter_service import CompanyFilterService
from .services.ak_filter_service import AkFilterService
from .services.subcontractors_to_filter_service import (
    SubcontractorToFilterService,
    SubcontractorFilterDTO,
)
from apps.contract_core.services.works_sum_report_service import WorksSumReportService
from apps.contract_core.export_excel.works_sum_report_excel import WorksSumReportExcelExporter

from apps.contract_core.services.status_sum_report_service import StatusSumReportService
from apps.contract_core.export_excel.status_sum_report_excel import StatusSumReportExcelExporter
from apps.contract_core.export_excel.contract_list_excel import export_contracts_to_excel
from apps.contract_core.export_excel.contract_detail_excel import export_contract_detail_to_excel

from apps.identity.mixins import PermissionRequiredMixin

from .mixins import ContractAccessMixin, ContractCreateUpdateMixin

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
    SigningStage, SigningStageControlSettings,
)
from .forms import (
    AkForm,
    CompanyForm,
    ContractForm,
    ContractSigningStageForm,
    ProtectionObjectFormSet,
    InterimActFormSet,
    FinalActForm, ProtectionObjectForm, InterimActForm,
)
from .services.history_service import ContractHistoryService
from apps.contract_core.services.signing_stage_report_service import (
    SigningStageReportService,
)
from apps.contract_core.services.toasts import toast_ok, toast_fail
from .export_excel import SigningStageReportExporter
from apps.contract_core.export_excel.companies_list_excel import export_companies_to_excel
from render_block import render_block_to_string




# ========== HTMX ЭНДПОИНТЫ ==========

# auditlog (История по договору)
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

# Подробные детали по договору
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
            'contract_objects__aks',        # <-- АК уже подгружены
            'final_act',
            'interim_acts',
            'signing_stage',
            'system_checks__system_type'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = context['contract']

        # Берём уже закэшированные prefetch-данные, чтобы не стучать в БД лишний раз
        contract_objects = list(contract.contract_objects.all())
        context['objects_count'] = len(contract_objects)

        # Собираем уникальные АК (на случай, если один АК привязан к нескольким объектам)
        seen_ak_ids = set()
        for obj in contract_objects:
            for ak in obj.aks.all():
                seen_ak_ids.add(ak.pk)
        context['aks_count'] = len(seen_ak_ids)

        return context

# Экспорт деталей договора в Excel
class ContractDetailExportExcelView(LoginRequiredMixin, ContractAccessMixin, DetailView):
    """Экспорт деталей договора в Excel"""
    model = Contract
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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        contract = self.object

        # Счётчики (как в детальной HTMX-вьюхе)
        contract_objects = list(contract.contract_objects.all())
        objects_count = len(contract_objects)

        seen_ak_ids = set()
        for obj in contract_objects:
            for ak in obj.aks.all():
                seen_ak_ids.add(ak.pk)
        aks_count = len(seen_ak_ids)

        filename = f"contract_{contract.number or contract.pk}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return export_contract_detail_to_excel(contract, objects_count, aks_count, filename=filename)


# Вьюхи для договоров
# ========== СПИСОЧНЫЕ ПРЕДСТАВЛЕНИЯ ==========

class ContractListView(LoginRequiredMixin, ListView):
    """Главная страница списка договоров"""
    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 10

    def _has_active_filters(self):
        ignored = {'page', 'csrfmiddlewaretoken', 'hx-request', 'hx-target', 'hx-current-url'}
        for key, value in self.request.GET.items():
            if key in ignored:
                continue
            if key == 'location' and value == 'active':
                continue
            if value and str(value).strip():
                return True
        return False

    def get_filtered_queryset(self):
        """Полный отфильтрованный queryset (используется для статистики и пагинации)"""
        base_queryset = Contract.objects.for_user(self.request.user)
        service = ContractFilterService(self.request, queryset=base_queryset)
        return service.filter()

    def get_queryset(self):
        filtered_qs = self.get_filtered_queryset()
        has_filters = self._has_active_filters()
        self._has_filters = has_filters

        if not has_filters:
            return filtered_qs[:10]  # лимит только без фильтров
        return filtered_qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['filter_data'] = ContractFilterService.get_filter_choices()
        context['districts'] = ContractFilterService.get_districts_by_region(
            self.request.GET.get('region')
        )
        context['signing_control_days'] = SigningStageControlSettings.get_settings().control_days

        has_filters = getattr(self, '_has_filters', self._has_active_filters())
        context['is_limited'] = not has_filters

        # === СТАТИСТИКА ===
        # 1. Для статистики всегда используем ПОЛНЫЙ отфильтрованный queryset
        full_qs = self.get_filtered_queryset()

        if not has_filters:
            # Без фильтров — статистика только по 10 отображаемым
            stats_qs = context['contracts']
        else:
            # При активных фильтрах — статистика по всем отфильтрованным
            stats_qs = full_qs

        aggregates = stats_qs.aggregate(
            count=Count('id'),
            total_sum=Sum('total_sum'),
            monthly_sum=Sum('monthly_sum'),
        )

        context['total_contracts'] = aggregates['count'] or 0
        context['total_count'] = context['total_contracts']
        context['total_sum'] = aggregates['total_sum'] or 0
        context['total_monthly_sum'] = aggregates['monthly_sum'] or 0

        context['total_objects'] = ProtectionObject.objects.filter(
            contract__in=stats_qs
        ).count()
        # счетчик, убирающий дубли АК (с помощью distinct)
        # context['total_aks'] = Ak.objects.filter(
        #     protection_objects__contract__in=stats_qs
        # ).distinct().count()

        # счетчик без distinct, т.е. если один и тот же АК в 2 объектах - посчитает за 2 АК
        context['total_aks'] = Ak.objects.filter(
            protection_objects__contract__in=stats_qs
        ).count()

        return context


class ContractListHtmxView(LoginRequiredMixin, ListView):
    """HTMX-эндпоинт для списка договоров"""
    model = Contract
    template_name = "contracts/contract_list.html"
    context_object_name = "contracts"
    paginate_by = 10

    def _has_active_filters(self):
        ignored = {'page', 'csrfmiddlewaretoken', 'hx-request', 'hx-target', 'hx-current-url'}
        for key, value in self.request.GET.items():
            if key in ignored:
                continue
            if key == 'location' and value == 'active':
                continue
            if value and str(value).strip():
                return True
        return False

    def get_filtered_queryset(self):
        base_queryset = Contract.objects.for_user(self.request.user)
        service = ContractFilterService(self.request, queryset=base_queryset)
        return service.filter()

    def get_queryset(self):
        return self.get_filtered_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        has_filters = self._has_active_filters()
        context['is_limited'] = not has_filters

        # === ДАННЫЕ ДЛЯ ФИЛЬТРА ===
        context['filter_data'] = ContractFilterService.get_filter_choices()
        context['districts'] = ContractFilterService.get_districts_by_region(
            self.request.GET.get('region')
        )

        # === СТАТИСТИКА ===
        full_qs = self.get_filtered_queryset()

        if not has_filters:
            stats_qs = context['contracts']
        else:
            stats_qs = full_qs

        aggregates = stats_qs.aggregate(
            count=Count('id'),
            total_sum=Sum('total_sum'),
            monthly_sum=Sum('monthly_sum'),
        )

        context['total_contracts'] = aggregates['count'] or 0
        context['total_count'] = context['total_contracts']
        context['total_sum'] = aggregates['total_sum'] or 0
        context['total_monthly_sum'] = aggregates['monthly_sum'] or 0

        context['total_objects'] = ProtectionObject.objects.filter(
            contract__in=stats_qs
        ).count()
        context['total_aks'] = Ak.objects.filter(
            protection_objects__contract__in=stats_qs
        ).distinct().count()
        context['signing_control_days'] = SigningStageControlSettings.get_settings().control_days

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.htmx:
            # Рендерим основной блок + OOB-обновления для фильтра и алерта
            blocks = ['contracts_list', 'filter_oob', 'limit_alert_oob']
            html_parts = []

            for block_name in blocks:
                try:
                    html_parts.append(
                        render_block_to_string(
                            self.template_name,
                            block_name,
                            context,
                            request=self.request
                        )
                    )
                except Exception:
                    # Если блок не найден, пропускаем
                    pass

            return HttpResponse('\n'.join(html_parts))
        return super().render_to_response(context, **response_kwargs)


class ContractExportExcelView(LoginRequiredMixin, View):
    """Экспорт отфильтрованного списка договоров в Excel"""

    def get(self, request, *args, **kwargs):
        base_queryset = Contract.objects.for_user(request.user)
        service = ContractFilterService(request, queryset=base_queryset)
        contracts = (
            service.filter()
            .select_related("customer", "executor", "work", "signing_stage__stage")
            .prefetch_related("contract_objects", "contract_objects__aks")
        )

        filename = f"contracts_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return export_contracts_to_excel(contracts, filename=filename)


# ========== CRUD ПРЕДСТАВЛЕНИЯ ==========

class ContractCreateView(LoginRequiredMixin, ContractCreateUpdateMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        self._save_action = self.request.POST.get('action', 'create_and_list')
        return super().form_valid(form)

    def get_success_url(self):
        action = getattr(self, '_save_action', 'create_and_list')

        if action == 'create_and_new':
            messages.success(self.request, "Договор успешно создан")
            return reverse_lazy('contract_core:contract_create')

        # По умолчанию — в список
        messages.success(self.request, "Договор успешно создан")
        return reverse_lazy('contract_core:contract_list')


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


class ContractMoveToTrashView(LoginRequiredMixin, ContractAccessMixin, DetailView):
    """Перемещение договора в корзину (is_trash = True)"""
    model = Contract
    pk_url_kwarg = 'pk'

    def post(self, request, *args, **kwargs):
        print("=== TRASH VIEW CALLED ===")
        contract = self.get_object()
        contract.is_trash = True
        contract.updater = request.user
        contract.save()
        messages.success(request, f"Договор №{contract.number} перемещён в корзину")
        return redirect('contract_core:contract_list')


class ContractRestoreView(LoginRequiredMixin, ContractAccessMixin, DetailView):
    """Восстановление договора из корзины (is_trash = False)"""
    model = Contract
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        # Восстановление видит ВСЕ договоры пользователя, включая корзинные
        return Contract.objects.for_user(self.request.user)

    def post(self, request, *args, **kwargs):
        print("=== CONTRACT RESTORE VIEW CALLED ===")
        contract = self.get_object()
        contract.is_trash = False
        contract.updater = request.user
        contract.save()
        messages.success(request, f"Договор №{contract.number} восстановлен")
        return redirect('contract_core:contract_list')


class ContractHardDeleteView(LoginRequiredMixin, ContractAccessMixin, DeleteView):
    """Полное удаление договора из базы (только для корзины)"""
    model = Contract
    template_name = "contracts/partials/contract_confirm_hard_delete_modal.html"
    pk_url_kwarg = 'pk'
    success_url = reverse_lazy('contract_core:contract_list')

    def get_queryset(self):
        # Удаление видит ВСЕ договоры пользователя, включая корзинные
        return Contract.objects.for_user(self.request.user)

    def delete(self, request, *args, **kwargs):
        print("=== CONTRACT HARD DELETE VIEW CALLED ===")
        contract = self.get_object()
        number = contract.number
        contract.delete()
        messages.success(request, f"Договор №{number} полностью удалён")
        return redirect(self.get_success_url())


# ========== ВСПОМОГАТЕЛЬНЫЕ ВЬЮХИ ДЛЯ ФОРМЫ ДОГОВОРА (добавление/редактирование)==========

class ContractFormFilterExecutorsView(LoginRequiredMixin, View):
    """HTMX: получить исполнителей по типу договора (для формы договора)"""

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

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_executor_select.html', {
            'executors': executors,
            'selected': selected,
        })


class ContractFormFilterWorksView(LoginRequiredMixin, View):
    """HTMX: получить работы по типу договора (для формы договора)"""

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

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_work_select.html', {
            'works': works,
            'selected': selected,
        })


class DynamicFieldsView(LoginRequiredMixin, View):
    """HTMX: обновление всех динамических полей при смене типа договора"""

    def get(self, request):
        # Проверяем, что это HTMX-запрос
        if not request.headers.get('HX-Request'):
            return HttpResponse("Требуется HTMX", status=400)

        contract_type = request.GET.get('type')
        user = request.user

        # Если тип не выбран — возвращаем пустые списки
        if not contract_type:
            return render(request, 'contracts/partials/partials_contract_form/_contract_form_dynamic_fields_edit.html', {
                'executors': [],
                'works': [],
                'contract_type': '',
                'selected_executor': '',
                'selected_work': '',
            })

        # Определяем фильтр по типу договора
        type_filter = Q()
        if contract_type in ['oneoff_licensee', 'longterm_to_licensee']:
            type_filter = Q(is_licensee=True)
        elif contract_type == 'oneoff_lab':
            type_filter = Q(is_laboratory=True)

        if user.is_superuser:
            # Для суперюзера показываем все компании, соответствующие типу договора
            executors = Company.objects.filter(
                type_filter
            ).distinct().order_by('name')
        else:
            # Для обычных пользователей: компания должна соответствовать типу
            # И пользователь должен быть активным сотрудником
            executors = Company.objects.filter(
                type_filter &
                Q(employees__user=user, employees__is_active=True)
            ).distinct().order_by('name')

        # Получаем работы (логика без изменений)
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

        # Получаем выбранные значения (если есть)
        selected_executor = request.GET.get('executor', '')
        selected_work = request.GET.get('work', '')

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_dynamic_fields_edit.html', {
            'executors': executors,
            'works': works,
            'contract_type': contract_type,
            'selected_executor': selected_executor,
            'selected_work': selected_work,
        })


# вьюха фильтра районов по региону в объектах защиты
class ContractFormFilterDistrictsByRegionView(LoginRequiredMixin, View):
    """HTMX: получить районы по выбранному региону (или пустой шаблон)"""

    def get(self, request):
        # Ищем region_id - может быть в 'region' или в поле формы типа 'contract_objects-0-region'
        region_id = request.GET.get('region')

        if not region_id:
            for key, value in request.GET.items():
                if key.endswith('-region'):
                    region_id = value
                    break

        field_name = request.GET.get('field_name', 'district')

        # Если регион не выбран - возвращаем пустой шаблон
        if not region_id:
            return render(request, 'contracts/partials/partials_contract_form/_contract_form_district_empty.html', {
                'field_name': field_name,
            })

        # Если регион выбран - получаем районы и возвращаем заполненный select
        districts = District.objects.filter(region_id=region_id).order_by('name')
        selected = request.GET.get('district', '')

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_district_field.html', {
            'districts': districts,
            'selected': selected,
            'field_name': field_name,
            'extra_class': request.GET.get('extra_class', ''),  # <-- добавили
        })

# Вьюха фильтра Заказчик
class ContractFormFilterCustomersView(LoginRequiredMixin, View):
    """HTMX: поиск заказчиков по названию или ИНН для формы договора"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        customers = Company.objects.none()

        if len(query) >= 2:
            customers = Company.objects.filter(
                is_customer=True
            ).filter(
                Q(name__icontains=query) | Q(inn__icontains=query)
            ).order_by('name')[:20]  # Ограничиваем 20 записями

        # Получаем текущее выбранное значение (если есть)
        selected = request.GET.get('customer', '')

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_customer_select.html', {
            'customers': customers,
            'selected': selected,
            'query': query,
        })


# ========== УПРАВЛЕНИЕ FORMSET'АМИ ЧЕРЕЗ HTMX ==========

class EmptyProtectionObjectFormView(LoginRequiredMixin, View):
    """
    Возвращает HTML пустой формы объекта защиты с правильным индексом.
    """

    def get(self, request):
        prefix = ProtectionObjectFormSet().prefix

        # --- защита от некорректного total_forms ---
        try:
            total_forms = int(request.GET.get('total_forms', 0))
        except (ValueError, TypeError):
            total_forms = 0

        total_forms = max(0, total_forms)
        # -------------------------------------------

        print(f"=== EmptyProtectionObjectFormView called, total_forms={total_forms} ===")

        form = ProtectionObjectForm(prefix=f"{prefix}-{total_forms}")
        form.fields['region'].queryset = Region.objects.all().order_by('name')
        form.fields['subcontractor'].queryset = Company.objects.filter(
            is_subcontractor=True
        ).order_by('name')

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_protection_object.html', {
            'form': form,
            'object': None,
            'index': total_forms,
            'all_regions': Region.objects.all().order_by('name'),
        })


class EmptyInterimActFormView(LoginRequiredMixin, View):
    """
    Возвращает HTML пустой формы промежуточного акта.
    Используется при нажатии "Добавить акт" через HTMX.
    """

    def get(self, request):
        prefix = InterimActFormSet().prefix
        total_forms = int(request.GET.get('total_forms', 0))

        # Создаем форму с правильным префиксом
        form = InterimActForm(prefix=f"{prefix}-{total_forms}")

        return render(request, 'contracts/partials/partials_contract_form/_contract_form_interim_act.html', {
            'form': form,
            'index': total_forms,
        })


class AkSearchView(LoginRequiredMixin, View):
    """HTMX: поиск АК по ID, номеру или названию с опциональным фильтром по району"""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        protection_object_id = request.GET.get('protection_object', '')

        # === НОВЫЙ РЕЖИМ: фильтр по региону и району (для панели выбора в объекте защиты) ===
        region_id = request.GET.get('region', '').strip()
        district_id = request.GET.get('district', '').strip()

        if region_id or district_id:
            if not region_id or not district_id:
                return render(request,
                    'contracts/partials/partials_contract_form/_contract_form_ak_selector_results.html',
                    {'error': 'Выберите регион и район', 'aks': []}
                )

            aks = Ak.objects.filter(district_id=district_id)

            if query:
                q_filter = Q(name__icontains=query)
                if query.isdigit():
                    q_filter |= Q(number=query) | Q(id=query)
                aks = aks.filter(q_filter)

            aks = aks.select_related('district__region').order_by('number')[:100]  # не более 100 АК при поиске

            return render(request,
                'contracts/partials/partials_contract_form/_contract_form_ak_selector_results.html',
                {'aks': aks, 'query': query}
            )

        # === СТАРЫЙ РЕЖИМ: быстрый поиск для уже сохранённых объектов (inline) ===
        aks = []
        if len(query) >= 2:
            q_filter = Q(name__icontains=query)
            if query.isdigit():
                q_filter |= Q(number=query) | Q(id=query)
            aks = Ak.objects.filter(q_filter)[:10]

        attached_ids = []
        if protection_object_id and protection_object_id != 'new':
            try:
                attached_ids = list(Ak.objects.filter(
                    protection_objects__id=protection_object_id
                ).values_list('id', flat=True))
            except (ValueError, ProtectionObject.DoesNotExist):
                pass

        return render(request,
            'contracts/partials/partials_contract_form/_contract_form_ak_search_results.html',
            {'aks': aks, 'attached_ids': attached_ids, 'query': query}
        )



class MarkSystemCheckView(LoginRequiredMixin, View):
    """Отметить проверку системы"""

    def post(self, request, contract_pk, system_type_pk):
        # from .models import SystemType, ContractSystemCheck

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







# ========== ВСПОМОГАТЕЛЬНЫЕ ВЬЮХИ ДЛЯ ФИЛЬТРА СПИСКА ДОГОВОРОВ ==========
# Эти вьюхи используются в contract_filter.html для динамической загрузки
# зависимых полей (работы по типу договора, районы по региону)

class FilterWorksView(LoginRequiredMixin, View):
    """HTMX: получить работы по типу договора (для фильтра списка)"""

    def get(self, request):
        contract_type = request.GET.get('contract_type')
        works = ContractFilterService.get_works_by_contract_type(contract_type)
        selected_work = request.GET.get('work', '')

        # ОБНОВЛЁННЫЙ ПУТЬ: шаблон переименован и перемещён
        return render(request, 'contracts/partials/partials_contract_list_filter/_work_select.html', {
            'works': works,
            'selected_work': selected_work
        })


class FilterDistrictsView(LoginRequiredMixin, View):
    """HTMX: получить районы по региону (для фильтра списка)"""

    def get(self, request):
        region_id = request.GET.get('region')
        districts = ContractFilterService.get_districts_by_region(region_id)
        selected_district = request.GET.get('district', '')

        # ОБНОВЛЁННЫЙ ПУТЬ: шаблон переименован и перемещён
        return render(request, 'contracts/partials/partials_contract_list_filter/_district_select.html', {
            'districts': districts,
            'selected_district': selected_district
        })



# Отчеты/////////////////////////////

# отчет по стадиям подписания
class ContractSigningStageReportsView(LoginRequiredMixin, TemplateView):
    """
    View для отображения отчёта по стадиям подписания договоров.
    """
    template_name = "reports/contract_signing_stage_reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        service = SigningStageReportService()
        report_data = service.get_report_data(self.request.user)

        context['report_data'] = report_data
        context['signing_stages'] = service.get_all_stages()
        context['control_days'] = service.get_control_days()  # Для примечания в шаблоне

        return context

# экспорт отчет по стадиям подписания в Excel
class ContractSigningStageReportsExcelView(LoginRequiredMixin, View):
    """
    View для экспорта отчёта по стадиям подписания в Excel.

    Ответственность:
    - Аутентификация/авторизация
    - Делегирование генерации Excel сервису
    - Формирование HTTP-ответа с файлом
    """

    def get(self, request, *args, **kwargs):
        # Получаем данные через существующий сервис
        report_service = SigningStageReportService()
        report_data = report_service.get_report_data(request.user)

        if not report_data:
            return HttpResponse("Нет данных для экспорта", status=404)

        # Генерируем Excel через отдельный сервис
        exporter = SigningStageReportExporter(
            report_data=report_data,
            stages=report_service.get_all_stages(),
            control_days=report_service.get_control_days()
        )

        excel_file = exporter.export()

        # Формируем ответ
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"signing_stages_report_{timezone.now().strftime('%Y-%m-%d')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(excel_file.getvalue())

        return response

        # Автоширина колонок
        for col in range(1, len(service.get_all_stages()) + 3):
            ws.column_dimensions[get_column_letter(col)].width = 18

        # Первая колонка шире (тип договора)
        ws.column_dimensions['A'].width = 30

        # Заморозка заголовков
        ws.freeze_panes = 'A3'

        # Ответ
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"signing_stages_report_{timezone.now().strftime('%Y-%m-%d')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        wb.save(response)
        return response


# Отчет Субподрядчики ТО (Техническое обслуживание)
class SubcontractorsToReportsView(LoginRequiredMixin, ListView):
    """
    Отчет по субподрядчикам ТО (Техническое обслуживание).
    Тонкая View — делегирует всю бизнес-логику сервису.
    """
    context_object_name = "protection_objects"

    def get_template_names(self):
        """Для HTMX-запросов возвращаем только фрагмент результатов"""
        if self.request.headers.get("HX-Request"):
            return ["reports/partials/subcontractors_to_reports_results.html"]
        return ["reports/subcontractors_to_reports_list.html"]

    def get_service(self) -> SubcontractorToFilterService:
        return SubcontractorToFilterService(self.request.user)

    def get_dto_from_request(self) -> SubcontractorFilterDTO:
        get = self.request.GET
        return SubcontractorFilterDTO(
            subcontractor_id=get.get("subcontractor_id", "").strip() or None,
            subcontractor_search=get.get("subcontractor_search", "").strip() or None,
            executor_ids=get.getlist("executor"),
            work_ids=get.getlist("work"),
            page=int(get.get("page", 1)),
        )

    def get_queryset(self):
        """
        Для HTMX-запросов queryset не нужен напрямую — данные берутся из сервиса.
        Но ListView требует его — возвращаем пустой, если фильтры не заданы.
        """
        dto = self.get_dto_from_request()
        service = self.get_service()

        if not service.has_active_filters(dto):
            return ProtectionObject.objects.none()

        return service.filter(dto)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dto = self.get_dto_from_request()
        service = self.get_service()

        ctx = service.get_context_data(dto)

        if service.has_active_filters(dto):
            result = service.get_report_result(dto, per_page=30)
            ctx = service.get_context_data(dto, result)

        context.update(ctx)
        return context

# Отчет по работам и суммам действующих договоров
class WorksSumReportView(LoginRequiredMixin, TemplateView):
    """Представление для отчета 'Работы и суммы' (HTML)."""
    template_name = "reports/works_sum_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        service = WorksSumReportService(self.request.user)
        report_data = service.generate_report()

        context.update(report_data)
        context['page_title'] = 'Отчет по работам и суммам действующих договоров'

        return context

# экспорт отчет по работам и суммам действующих договоров в Excel
class WorksSumReportExcelView(LoginRequiredMixin, View):
    """Представление для экспорта отчета 'Работы и суммы' в Excel."""

    def get(self, request, *args, **kwargs):
        exporter = WorksSumReportExcelExporter(request.user)
        output = exporter.export()

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{exporter.get_filename()}"'

        return response


# Отчет по статусам и суммам неархивных договоров
class StatusSumReportView(LoginRequiredMixin, TemplateView):
    """HTML-отчет по статусам и суммам."""
    template_name = "reports/status_sum_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        service = StatusSumReportService(self.request.user)
        report_data = service.generate_report()

        context.update(report_data)
        context['page_title'] = 'Отчет по статусам и общим суммам неархивных договоров'

        return context

# экспорт отчета по статусам и суммам неархивных договоров в Excel
class StatusSumReportExcelView(LoginRequiredMixin, View):
    """Экспорт отчета по статусам в Excel."""

    def get(self, request, *args, **kwargs):
        exporter = StatusSumReportExcelExporter(request.user)
        output = exporter.export()

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{exporter.get_filename()}"'

        return response






# Вьюхи Справочник AK
class AkListView(LoginRequiredMixin, ListView):
    """Список абонентских комплектов (АК)"""
    model = Ak
    template_name = "catalogs/ak_list.html"
    context_object_name = "aks"
    paginate_by = 25

    def get_paginate_by(self, queryset):
        filter_service = AkFilterService(self.request.GET)
        return self.paginate_by if filter_service.has_active_filters() else 10

    def get_ordering(self):
        """Динамическое определение сортировки."""
        filter_service = AkFilterService(self.request.GET)

        # При активных фильтрах: регион → район → номер АК
        if filter_service.has_active_filters():
            return ['district__region__name', 'district__name', 'number']
        # Без фильтров: последние добавленные
        return ['-id']

    def get_queryset(self):
        filter_service = AkFilterService(self.request.GET)
        qs = filter_service.filter()
        # Применяем сортировку
        ordering = self.get_ordering()
        qs = qs.order_by(*ordering)
        # Применяем срез только если нет фильтров
        if not filter_service.has_active_filters():
            qs = qs[:10]
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_service = AkFilterService(self.request.GET)
        context.update(filter_service.get_context_data())

        # Флаг для шаблона — показывать ли сообщение о лимите
        context['is_limited'] = not filter_service.has_active_filters()

        # Флаг для шаблона — применена ли группировка
        context['is_grouped'] = filter_service.has_active_filters()

        # Права пользователя для шаблона
        user = self.request.user
        context['can_manage_aks'] = user.can_manage_aks()

        # Все регионы для выпадающего списка
        context['regions'] = Region.objects.all().order_by('name')
        # Районы для выбранного региона
        region_id = self.request.GET.get('region', '').strip()
        if region_id and region_id.isdigit():
            context['districts'] = District.objects.filter(region_id=int(region_id)).order_by('name')
        else:
            context['districts'] = District.objects.none()
        return context

class AkCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    """Создание АК"""
    model = Ak
    form_class = AkForm
    template_name = "catalogs/partials/ak_form_modal.html"
    success_url = reverse_lazy('contract_core:ak_list')
    permission = 'can_manage_aks'  # ← проверка через миксин

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = "Добавить АК"
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('HX-Request'):
            # modal_id указываем именно тот, который используется в шаблоне АК
            return toast_ok(
                refresh_url=reverse_lazy('contract_core:ak_list'),
                modal_id="akModal"
            )
        # Для обычного (не-HTMX) запроса
        messages.success(self.request, "АК успешно добавлен!")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return toast_fail(modal_id="akModal")
        return self.render_to_response(self.get_context_data(form=form))

class AkUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Ak
    form_class = AkForm
    template_name = "catalogs/partials/ak_form_modal.html"
    success_url = reverse_lazy('contract_core:ak_list')
    permission = 'can_manage_aks'  # ← добавить проверку прав

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = f"Редактировать АК №{self.object.number}"
        return context

    def form_valid(self, form):
        form.save()

        if self.request.headers.get('HX-Request'):
            return toast_ok(
                refresh_url=reverse_lazy('contract_core:ak_list'),
                modal_id="akModal"
            )

        messages.success(self.request, "АК успешно обновлён!")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return toast_fail(modal_id="akModal")
        return self.render_to_response(self.get_context_data(form=form))

class AkDetailHtmxView(LoginRequiredMixin, DetailView):
    """HTMX эндпоинт для модального окна детальной информации об АК (только просмотр — без прав)"""
    model = Ak
    template_name = "catalogs/partials/ak_detail_modal.html"
    context_object_name = "ak"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        # Для HTMX-запросов возвращаем только контент модалки
        if request.headers.get('HX-Request'):
            return response

        # Для прямого захода - редирект на список
        return HttpResponseRedirect(reverse_lazy('contract_core:ak_list'))

# для модального окна статистики по АК
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
        from apps.contract_core.services.company_filter_service import CompanyFilterService
        filter_service = CompanyFilterService(self.request.GET)
        if filter_service.has_active_filters():
            return self.paginate_by
        return 10

    def get_queryset(self):
        from apps.contract_core.services.company_filter_service import CompanyFilterService
        filter_service = CompanyFilterService(self.request.GET)
        qs = filter_service.filter()

        if not filter_service.has_active_filters():
            qs = qs[:10]

        return qs

    def get_context_data(self, **kwargs):
        from apps.contract_core.services.company_filter_service import CompanyFilterService
        context = super().get_context_data(**kwargs)
        filter_service = CompanyFilterService(self.request.GET)
        context.update(filter_service.get_context_data())
        context['is_limited'] = not filter_service.has_active_filters()

        # Права пользователя для шаблона
        user = self.request.user
        context['can_manage_companies'] = user.can_manage_companies()

        return context


class CompaniesListExcelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        from apps.contract_core.services.company_filter_service import CompanyFilterService
        filter_service = CompanyFilterService(request.GET)
        companies = filter_service.filter()

        file_obj, filename = export_companies_to_excel(companies)

        response = FileResponse(
            file_obj,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# c HTMX
class CompanyCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = Company
    form_class = CompanyForm
    template_name = "catalogs/partials/company_form_modal.html"
    success_url = reverse_lazy('contract_core:companies_list')
    permission = 'can_manage_companies'  # ← проверка прав

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = "Добавить компанию"
        return context

    def form_valid(self, form):
        self.object = form.save()

        if self.request.headers.get('HX-Request'):
            return toast_ok(
                refresh_url=reverse_lazy('contract_core:companies_list')
            )

        messages.success(self.request, "Успешное сохранение!")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return toast_fail()

        return self.render_to_response(self.get_context_data(form=form))


# c HTMX
class CompanyUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = "catalogs/partials/company_form_modal.html"
    success_url = reverse_lazy('contract_core:companies_list')
    permission = 'can_manage_companies'  # ← проверка прав

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modal_title'] = f"Редактировать компанию: {self.object.name}"
        return context

    def form_valid(self, form):
        form.save()

        if self.request.headers.get('HX-Request'):
            return toast_ok(refresh_url=reverse_lazy('contract_core:companies_list'))

        messages.success(self.request, "Компания успешно обновлена!")
        return HttpResponseRedirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return toast_fail()

        return self.render_to_response(self.get_context_data(form=form))


class CompanyDetailHtmxView(LoginRequiredMixin, DetailView):
    """HTMX эндпоинт для модального окна детальной информации о компании."""
    model = Company
    template_name = "catalogs/partials/company_detail_modal.html"
    context_object_name = "company"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        # Для HTMX-запросов возвращаем только контент модалки
        if request.headers.get('HX-Request'):
            return response

        # Для прямого захода - редирект на список
        return HttpResponseRedirect(reverse_lazy('contract_core:companies_list'))


class CompanyStatsView(LoginRequiredMixin, View):
    """Возвращает статистику по компаниям для модального окна."""

    def get(self, request, *args, **kwargs):
        stats = Company.objects.aggregate(
            total=Count('id'),
            customers=Count('id', filter=Q(is_customer=True)),
            licensees=Count('id', filter=Q(is_licensee=True)),
            laboratories=Count('id', filter=Q(is_laboratory=True)),
            subcontractors=Count('id', filter=Q(is_subcontractor=True)),
            notification_agreed=Count('id', filter=Q(notification_agreed=True)),
        )

        return render(request, 'catalogs/partials/company_stats_modal.html', stats)




# Вьюхи для Справочника Стадии подписания
class SigningStageListView(ListView):
    """Справочник стадий подписания договора."""
    model = SigningStage
    template_name = "catalogs/signing_stage_list.html"
    context_object_name = 'stages'
    paginate_by = 50

    def get_queryset(self):
        return SigningStage.objects.all().order_by('order', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Справочник стадий подписания"
        context['page_description'] = "Просмотр стадий жизненного цикла договора"
        return context

# Вьюхи для Справочника Работы
class WorkListView(ListView):
    """Справочник видов работ с группировкой по типам."""
    model = Work
    template_name = "catalogs/work_list.html"
    context_object_name = 'works'
    paginate_by = 50

    def get_queryset(self):
        return Work.objects.all().order_by('work_type', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Справочник видов работ"
        context['page_description'] = "Каталог работ, сгруппированных по типам выполнения"

        # Группировка работ по типам (только для текущей страницы)
        works_grouped = defaultdict(list)

        for work in context['works']:
            works_grouped[work.work_type].append(work)

        # Формируем список групп с сохранением порядка WorkType.choices
        grouped_data = []
        for type_key, type_label in Work.WorkType.choices:
            if type_key in works_grouped:
                grouped_data.append({
                    'type_key': type_key,
                    'type_label': type_label,
                    'items': works_grouped[type_key]
                })

        context['grouped_works'] = grouped_data
        return context

# Вьюхи для Справочника Системы
class SystemTypeListView(ListView):
    """Справочник типов систем."""
    model = SystemType
    template_name = "catalogs/system_type_list.html"
    context_object_name = 'system_types'
    paginate_by = 50

    def get_queryset(self):
        return SystemType.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Справочник типов систем"
        context['page_description'] = "Каталог систем для проверки и отметки"
        return context
