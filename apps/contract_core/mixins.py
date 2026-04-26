# apps/contract_core/mixins.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.shortcuts import redirect
from django.views.generic.base import ContextMixin
from .forms import (
    ProtectionObjectFormSet,
    InterimActFormSet,
    FinalActForm,
    ContractSigningStageForm,
    ContractSystemCheckFormSet,
)
from .models import ContractSystemCheck, FinalAct, SystemType, SigningStage, Region


# Миксин для вьюх (проверка допусков)
class ContractAccessMixin:
    """
    Миксин проверяет, имеет ли пользователь доступ к контракту.
    Применяйте ко всем представлениям, работающим с одним контрактом.
    """

    def get_queryset(self):
        """Возвращает queryset с учетом прав пользователя"""
        # Получаем базовый queryset от родительского класса (DetailView, ListView и т.д.)
        # Если родитель не имеет get_queryset (например, View), берём из модели
        parent_get_queryset = getattr(super(), 'get_queryset', None)

        if parent_get_queryset:
            try:
                queryset = parent_get_queryset()
            except Exception:
                # Если DetailView ругается на отсутствие model/queryset,
                # но model есть у self — используем его
                queryset = self.model._default_manager.all()
        else:
            # Родитель — обычный View без get_queryset, берём из модели
            queryset = self.model._default_manager.all()

        # Применяем фильтр прав пользователя
        if hasattr(queryset, 'for_user'):
            return queryset.for_user(self.request.user)

        # Fallback: если for_user недоступен (не должно произойти для Contract)
        return queryset

    def get_object(self, queryset=None):
        """Получает объект с проверкой доступа"""
        if queryset is None:
            queryset = self.get_queryset()

        # Получаем pk из URL
        pk = self.kwargs.get(self.pk_url_kwarg)

        if pk is None:
            raise AttributeError(
                f"View {self.__class__.__name__} must be called with "
                f"an object pk (expected '{self.pk_url_kwarg}' in URL)"
            )

        # get_object_or_404 с ограниченным queryset вернет 404, если нет доступа
        obj = get_object_or_404(queryset, pk=pk)
        return obj


# Миксин для вьюх
class ContractCreateUpdateMixin:
    """Миксин для создания и редактирования договора с inline formsets"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Активные системы понадобятся в обоих режимах
        active_systems = list(SystemType.objects.filter(is_active=True).order_by('name'))
        context['all_regions'] = Region.objects.all().order_by('name')

        if self.request.POST:
            context['protection_object_formset'] = ProtectionObjectFormSet(
                self.request.POST, instance=self.object
            )
            context['signing_stage_form'] = ContractSigningStageForm(
                self.request.POST,
                instance=self.object.signing_stage if self.object and hasattr(self.object, 'signing_stage') else None
            )
            context['interim_act_formset'] = InterimActFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
            context['final_act_form'] = FinalActForm(
                self.request.POST, self.request.FILES,
                instance=self.object.final_act if self.object and hasattr(self.object, 'final_act') else None
            )

            # Formset отметок по системам (instance=None при создании допустимо для валидации)
            context['system_check_formset'] = ContractSystemCheckFormSet(
                self.request.POST,
                instance=self.object,
                available_systems=active_systems,
                prefix='sys_checks'
            )
        else:
            context['protection_object_formset'] = ProtectionObjectFormSet(instance=self.object)

            # Стадия подписания
            if self.object and hasattr(self.object, 'signing_stage'):
                context['signing_stage_form'] = ContractSigningStageForm(instance=self.object.signing_stage)
            else:
                initial_stage = SigningStage.objects.order_by('order').first()
                context['signing_stage_form'] = ContractSigningStageForm(
                    initial={'stage': initial_stage.id if initial_stage else None}
                )

            context['interim_act_formset'] = InterimActFormSet(instance=self.object)
            context['final_act_form'] = FinalActForm(
                instance=self.object.final_act if self.object and hasattr(self.object, 'final_act') else None
            )

            # === ОТМЕТКИ ПО СИСТЕМАМ ===
            if self.object:
                # РЕДАКТИРОВАНИЕ: существующие отметки + новые системы из справочника
                existing_qs = ContractSystemCheck.objects.filter(
                    contract=self.object,
                    system_type__is_active=True
                ).select_related('system_type').order_by('system_type__name')

                existing_ids = set(existing_qs.values_list('system_type_id', flat=True))
                missing_systems = [s for s in active_systems if s.id not in existing_ids]

                context['system_check_formset'] = ContractSystemCheckFormSet(
                    instance=self.object,
                    queryset=existing_qs,
                    available_systems=missing_systems,
                    prefix='sys_checks'
                )
            else:
                # СОЗДАНИЕ: формы для всех активных систем
                context['system_check_formset'] = ContractSystemCheckFormSet(
                    instance=None,
                    queryset=ContractSystemCheck.objects.none(),
                    available_systems=active_systems,
                    prefix='sys_checks'
                )

        return context

    def get_system_checks(self):
        """Получить или создать отметки по системам для договора"""
        if not self.object:
            return []

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
        # ВРЕМЕННАЯ ОТЛАДКА
        print("=== POST DATA ===")
        for k, v in self.request.POST.items():
            if 'ak_ids' in k or 'contract_objects' in k:
                print(f"{k}: {v}")

        context = self.get_context_data()
        protection_formset = context['protection_object_formset']
        signing_form = context['signing_stage_form']
        interim_formset = context['interim_act_formset']
        final_act_form = context['final_act_form']
        system_check_formset = context['system_check_formset']

        is_valid = True

        if not protection_formset.is_valid():
            is_valid = False
        if not signing_form.is_valid():
            is_valid = False
        if not interim_formset.is_valid():
            is_valid = False
        if not final_act_form.is_valid():
            is_valid = False
        if not system_check_formset.is_valid():
            is_valid = False

        if not is_valid:
            return self.render_to_response(self.get_context_data(form=form))

        # Запоминаем, создаём ли новый договор
        is_new_contract = not form.instance.pk

        # 1. Сохраняем основной договор
        self.object = form.save()

        # 2. Объекты защиты
        protection_formset.instance = self.object
        protection_formset.save()

        # Привязка АК ко всем сохранённым объектам защиты
        for po_form in protection_formset.forms:
            print(f"Form {po_form.prefix}: ak_ids = {po_form.cleaned_data.get('ak_ids')}")
            if po_form in protection_formset.deleted_forms:
                continue
            ak_ids = po_form.cleaned_data.get('ak_ids', [])
            if ak_ids is not None:
                po_form.instance.aks.set(ak_ids)

        # 3. Стадия подписания
        signing_stage = signing_form.save(commit=False)
        signing_stage.contract = self.object
        signing_stage.save()

        # 4. Итоговый акт
        final_act = final_act_form.save(commit=False)
        final_act.contract = self.object
        defaults = {
            'present': final_act.present,
            'date': final_act.date,
            'file': final_act.file,
            'note': final_act.note,
        }
        if final_act_form.cleaned_data.get('present'):
            if not final_act.checked_by:
                final_act.checked_by = self.request.user
                final_act.checked_at = timezone.now()
            defaults['checked_by'] = final_act.checked_by
            defaults['checked_at'] = final_act.checked_at
        else:
            defaults['checked_by'] = None
            defaults['checked_at'] = None
        FinalAct.objects.update_or_create(contract=self.object, defaults=defaults)

        # 5. Промежуточные акты
        interim_formset.instance = self.object
        interim_formset.save()

        # 6. ОТМЕТКИ ПО СИСТЕМАМ
        system_check_formset.instance = self.object

        if is_new_contract:
            # Ручная обработка при создании — защита от дублей и unique constraint
            saved_system_ids = set()
            for form in system_check_formset.forms:
                if not hasattr(form, 'cleaned_data') or not form.cleaned_data:
                    continue
                if form.cleaned_data.get('DELETE'):
                    continue  # при создании нечего удалять

                system_type = form.cleaned_data.get('system_type')
                if not system_type:
                    continue

                st_id = system_type.pk if hasattr(system_type, 'pk') else system_type
                if st_id in saved_system_ids:
                    continue  # пропускаем дубль внутри запроса
                saved_system_ids.add(st_id)

                last_checked = form.cleaned_data.get('last_checked')
                note = form.cleaned_data.get('note', '')

                ContractSystemCheck.objects.update_or_create(
                    contract=self.object,
                    system_type=system_type,
                    defaults={
                        'last_checked': last_checked,
                        'note': note,
                        'checked_by': self.request.user if last_checked else None,
                    }
                )
        else:
            # При редактировании стандартный save() работает корректно
            saved_checks = system_check_formset.save()
            for obj in saved_checks:
                if obj.last_checked and not obj.checked_by:
                    obj.checked_by = self.request.user
                    obj.save(update_fields=['checked_by'])
                elif not obj.last_checked and obj.checked_by:
                    obj.checked_by = None
                    obj.save(update_fields=['checked_by'])
            # Удаление отмеченных форм
            for obj in system_check_formset.deleted_objects:
                obj.delete()

        return redirect(self.get_success_url())