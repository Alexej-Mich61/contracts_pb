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
)
from .models import ContractSystemCheck, FinalAct, SystemType, SigningStage



# Миксин для вьюх (проверка допусков)
class ContractAccessMixin:
    """
    Миксин проверяет, имеет ли пользователь доступ к контракту.
    Применяйте ко всем представлениям, работающим с одним контрактом.
    """

    def get_queryset(self):
        """Возвращает queryset с учетом прав пользователя"""
        # Получаем queryset от родительского класса (или создаем новый)
        queryset = getattr(super(), 'get_queryset', lambda: self.model.objects)()

        # Если это уже QuerySet от модели Contract
        if hasattr(queryset, 'for_user'):
            return queryset.for_user(self.request.user)

        # Если нет — берем напрямую
        return self.model.objects.for_user(self.request.user)

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

        if self.request.POST:
            context['protection_object_formset'] = ProtectionObjectFormSet(
                self.request.POST, instance=self.object
            )
            context['signing_stage_form'] = ContractSigningStageForm(
                self.request.POST,
                instance=self.object.signing_stage if self.object and hasattr(self.object, 'signing_stage') else None
            )

            # ВСЕГДА инициализируем формы актов (и при создании, и при редактировании)
            context['interim_act_formset'] = InterimActFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
            context['final_act_form'] = FinalActForm(
                self.request.POST, self.request.FILES,
                instance=self.object.final_act if self.object and hasattr(self.object, 'final_act') else None
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

            # ВСЕГДА инициализируем формы актов (даже при создании договора)
            context['interim_act_formset'] = InterimActFormSet(instance=self.object)
            context['final_act_form'] = FinalActForm(
                instance=self.object.final_act if self.object and hasattr(self.object, 'final_act') else None
            )

            # Отметки по системам: при редактировании — реальные данные, при создании — пустой список
            if self.object:
                context['system_checks'] = self.get_system_checks()
            else:
                context['system_checks'] = []

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
        context = self.get_context_data()
        protection_formset = context['protection_object_formset']
        signing_form = context['signing_stage_form']
        interim_formset = context['interim_act_formset']
        final_act_form = context['final_act_form']

        # Отладка: проверяем данные POST
        print("=== POST DATA ===")
        print(self.request.POST)
        print("=== FILES ===")
        print(self.request.FILES)

        print("=== ProtectionObjectFormSet data ===")
        print(protection_formset.data if hasattr(protection_formset, 'data') else 'no data')
        print("TOTAL FORMS:", self.request.POST.get('protection_objects-TOTAL_FORMS', 'NOT FOUND'))

        is_valid = True

        if not protection_formset.is_valid():
            is_valid = False
            print("=== ProtectionObjectFormSet ERRORS ===")
            print(protection_formset.errors)
            print("Non-form errors:", protection_formset.non_form_errors())
        else:
            print("=== ProtectionObjectFormSet is VALID ===")
            print("Cleaned data:", protection_formset.cleaned_data)

        if not signing_form.is_valid():
            is_valid = False
        if not interim_formset.is_valid():
            is_valid = False
        if not final_act_form.is_valid():
            is_valid = False

        if not is_valid:
            print("=== FORM NOT VALID, returning errors ===")
            return self.render_to_response(self.get_context_data(form=form))

        # Сохраняем основной договор
        self.object = form.save()
        print(f"=== Contract saved: {self.object.pk} ===")

        # Сохраняем formset объектов защиты
        protection_formset.instance = self.object
        saved_objects = protection_formset.save()
        print(f"=== Saved {len(saved_objects)} protection objects ===")
        print("Saved objects:", saved_objects)

        # Сохраняем стадию подписания
        signing_stage = signing_form.save(commit=False)
        signing_stage.contract = self.object
        signing_stage.save()

        # Сохраняем итоговый акт через update_or_create
        final_act = final_act_form.save(commit=False)
        final_act.contract = self.object

        # Подготавливаем defaults
        defaults = {
            'present': final_act.present,
            'date': final_act.date,
            'file': final_act.file,
            'note': final_act.note,
        }

        # Если акт отмечен как сформированный и еще не было отметки — ставим текущую дату
        if final_act_form.cleaned_data.get('present'):
            if not final_act.checked_by:
                final_act.checked_by = self.request.user
                final_act.checked_at = timezone.now()
            # Если уже был отмечен ранее — оставляем старые значения (или обновляем при желании)
            defaults['checked_by'] = final_act.checked_by
            defaults['checked_at'] = final_act.checked_at
        else:
            # Если акт не отмечен — сбрасываем отметку
            defaults['checked_by'] = None
            defaults['checked_at'] = None

        FinalAct.objects.update_or_create(
            contract=self.object,
            defaults=defaults
        )

        # Сохраняем промежуточные акты (даже при создании договора)
        interim_formset.instance = self.object
        interim_formset.save()

        return redirect(self.get_success_url())