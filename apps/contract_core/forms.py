# apps/contract_core/forms.py
from django import forms
from django.db.models import Q
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from .validators import file_validator

from .models import (
    Ak,
    Region,
    District,
    Company,
    Work,
    Contract,
    ContractSigningStage,
    ContractSystemCheck,
    ProtectionObject,
    FinalAct,
    InterimAct,
)



# ========== СПРАВОЧНИКИ ==========
# Формы для управления справочными данными (АК, Компании)

# форма АК в справочнике
class AkForm(forms.ModelForm):
    class Meta:
        model = Ak
        fields = ['number', 'name', 'address', 'district']
        widgets = {
            'number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '99999999'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['district'].queryset = District.objects.select_related('region').order_by('region__name', 'name')
        self.fields['district'].label_from_instance = lambda obj: f"{obj.region.name} – {obj.name}"


# форма КОМПАНИИ
class CompanyForm(forms.ModelForm):
    """
    Форма компании
    """

    class Meta:
        model = Company
        fields = [
            'name', 'inn', 'email', 'phone', 'description', 'fias_code',
            'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor',
            'notification_agreed'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'inn': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Краткое описание компании...',
                'maxlength': 500
            }),
            'fias_code': forms.TextInput(attrs={'class': 'form-control'}),
            'is_customer': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_licensee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_laboratory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_subcontractor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_agreed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        roles = [
            cleaned_data.get('is_customer'),
            cleaned_data.get('is_licensee'),
            cleaned_data.get('is_laboratory'),
            cleaned_data.get('is_subcontractor'),
        ]
        if not any(roles):
            raise forms.ValidationError("Необходимо выбрать хотя бы одну роль.")
        return cleaned_data


# ========== ДОГОВОР (ОСНОВНОЕ) ==========


# Основная форма договора и связанные с ней
# форма ДОГОВОРА (контракта)
class ContractForm(forms.ModelForm):
    """
    Форма договора.
    Поля executor и work заполняются динамически через HTMX (DynamicFieldsView).
    Поле customer заполняется через поиск (фильтрацию).
    """

    class Meta:
        model = Contract
        fields = [
            'type', 'number', 'date_concluded',
            'customer', 'date_start', 'date_end', 'executor', 'work',
            'note', 'file', 'total_sum', 'monthly_sum', 'advance', 'is_paid'
        ]
        widgets = {
            'type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 45/2024',
            }),
            'date_concluded': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d'
            ),
            'date_start': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d'
            ),
            'date_end': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d'
            ),
            'customer': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_customer',
            }),
            'executor': forms.Select(attrs={
                'class': 'form-select',
            }),
            'work': forms.Select(attrs={
                'class': 'form-select',
            }),
            'note': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Дополнительная информация по договору...',
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
            'total_sum': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'monthly_sum': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'advance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'is_paid': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
        }
        help_texts = {
            'type': 'Выберите тип договора для активации связанных полей',
            'number': 'Внутренний или внешний номер договора',
            'date_concluded': 'Дата подписания договора',
            'date_start': 'Начало периода действия договора',
            'date_end': 'Окончание периода действия договора',
            'total_sum': 'Общая сумма договора (руб.)',
            'monthly_sum': 'Ежемесячная сумма для долгосрочных договоров',
            'advance': 'Сумма авансового платежа',
            'file': 'PDF, DOC, DOCX, до 100 МБ',
            'customer': 'Выберите заказчика из списка или воспользуйтесь поиском',
            'is_paid': 'Отметьте, если договор полностью оплачен',
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        # Устанавливаем дефолтные значения только для НОВЫХ договоров
        if not self.instance.pk:
            today = timezone.now().date()
            self.fields['date_concluded'].initial = today
            self.fields['date_start'].initial = today

            if not self.data:
                self.fields['customer'].queryset = Company.objects.none()
                self.fields['customer'].choices = [('', '— Введите название или ИНН и нажмите "Найти" —')]
                self.fields['executor'].queryset = Company.objects.none()
                self.fields['work'].queryset = Work.objects.none()
            else:
                self.fields['customer'].queryset = Company.objects.filter(is_customer=True)
                self.fields['executor'].queryset = Company.objects.filter(
                    Q(is_licensee=True) | Q(is_laboratory=True)
                )
                self.fields['work'].queryset = Work.objects.filter(is_active=True)

        else:
            # ===== РЕЖИМ РЕДАКТИРОВАНИЯ =====
            if self.is_bound:
                # POST/PUT/PATCH — даём полный queryset для валидации,
                # т.к. пользователь мог изменить значения через HTMX
                self.fields['customer'].queryset = Company.objects.filter(is_customer=True)
                self.fields['executor'].queryset = Company.objects.filter(
                    Q(is_licensee=True) | Q(is_laboratory=True)
                )
                self.fields['work'].queryset = Work.objects.filter(is_active=True)
            else:
                # GET — readonly-режим, показываем только текущие значения
                if self.instance.customer:
                    self.fields['customer'].queryset = Company.objects.filter(pk=self.instance.customer.pk)
                    self.fields['customer'].initial = self.instance.customer_id

                if self.instance.executor:
                    self.fields['executor'].queryset = Company.objects.filter(pk=self.instance.executor.pk)
                    self.fields['executor'].initial = self.instance.executor_id

                if self.instance.work:
                    self.fields['work'].queryset = Work.objects.filter(pk=self.instance.work.pk)
                    self.fields['work'].initial = self.instance.work_id

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get('customer')

        # Проверка заказчика
        if not customer:
            self.add_error('customer', 'Необходимо выбрать заказчика')

        # Валидация дат
        date_start = cleaned_data.get('date_start')
        date_end = cleaned_data.get('date_end')

        if date_start and date_end and date_end < date_start:
            self.add_error('date_end', 'Дата окончания не может быть раньше даты начала')

        return cleaned_data

    # def clean_total_sum(self):
    #     val = self.cleaned_data.get('total_sum')
    #     if val is not None and val < 0:
    #         raise forms.ValidationError("Сумма не может быть отрицательной")
    #     return val
    #
    # def clean_monthly_sum(self):
    #     val = self.cleaned_data.get('monthly_sum')
    #     if val is not None and val < 0:
    #         raise forms.ValidationError("Сумма не может быть отрицательной")
    #     return val
    #
    # def clean_advance(self):
    #     val = self.cleaned_data.get('advance')
    #     if val is not None and val < 0:
    #         raise forms.ValidationError("Аванс не может быть отрицательным")
    #     return val


class ContractSigningStageForm(forms.ModelForm):
    """Форма стадии подписания договора (inline)"""

    class Meta:
        model = ContractSigningStage
        fields = ['stage', 'note']
        widgets = {
            'stage': forms.Select(attrs={'class': 'form-select'}),
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Комментарий к текущей стадии...',
                'maxlength': 200,
            }),
        }
        labels = {
            'stage': 'Текущая стадия',
            'note': 'Примечание',
        }


class FinalActForm(forms.ModelForm):
    """Форма итогового акта (inline)"""

    class Meta:
        model = FinalAct
        fields = ['present', 'date', 'file', 'note']
        widgets = {
            'present': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
            'date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                },
                format='%Y-%m-%d'  # <-- добавить для отображении даты при редактировании
            ),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Примечание к акту...',
                'maxlength': 200,
            }),
        }
        labels = {
            'present': 'Акт сформирован',
            'date': 'Дата акта',
            'file': 'Файл акта',
            'note': 'Примечание',
        }


class InterimActForm(forms.ModelForm):
    """Форма промежуточного акта (formset)"""

    class Meta:
        model = InterimAct
        fields = ['title', 'date', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Акт этапа 1',
            }),
            'date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                },
                format='%Y-%m-%d'  # <-- добавить
            ),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
        }


# Formset для промежуточных актов
InterimActFormSet = forms.inlineformset_factory(
    Contract,
    InterimAct,
    form=InterimActForm,
    extra=0,  # <-- Изменить с 1 на 0 (HTMX будет добавлять формы динамически)
    can_delete=True,
    min_num=0,
    max_num=20,
)

# ========== ОТМЕТКИ ПО СИСТЕМАМ (inline formset) ==========

class ContractSystemCheckForm(forms.ModelForm):
    """
    Форма одной отметки по системе.
    Чекбокс mark_today — удобная альтернатива ручному вводу даты.
    """
    mark_today = forms.BooleanField(
        required=False,
        label="Отметить",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = ContractSystemCheck
        fields = ['system_type', 'last_checked', 'note', 'mark_today']
        widgets = {
            'system_type': forms.HiddenInput(),
            'last_checked': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control form-control-sm'},
                format='%Y-%m-%d'
            ),
            'note': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Примечание...',
                'maxlength': 200
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['last_checked'].required = False
        self.fields['note'].required = False
        self.fields['system_type'].required = False

        # Если запись уже отмечена — включаем чекбокс
        if self.instance and self.instance.pk and self.instance.last_checked:
            self.fields['mark_today'].initial = True

    def clean(self):
        cleaned_data = super().clean()
        mark_today = cleaned_data.get('mark_today')
        last_checked = cleaned_data.get('last_checked')

        # Чекбокс включён, а даты нет — ставим сегодня
        if mark_today and not last_checked:
            cleaned_data['last_checked'] = timezone.now().date()
        # Чекбокс снят — сбрасываем дату (если форма не на удаление)
        elif not mark_today and not cleaned_data.get('DELETE'):
            cleaned_data['last_checked'] = None

        return cleaned_data


class BaseContractSystemCheckFormSet(forms.BaseInlineFormSet):
    """
    Подставляет system_type в extra-формы.
    extra вычисляется ДО super().__init__(), иначе Django создаст 0 форм.
    """

    def __init__(self, *args, **kwargs):
        self.available_systems = list(kwargs.pop('available_systems', []))
        # ВАЖНО: до super(), чтобы BaseFormSet увидел правильное число форм
        self.extra = len(self.available_systems)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        if i >= self.initial_form_count():
            extra_idx = i - self.initial_form_count()
            if extra_idx < len(self.available_systems):
                system = self.available_systems[extra_idx]
                if 'instance' not in kwargs:
                    kwargs['instance'] = self.model()
                kwargs['instance'].system_type = system
                if 'initial' not in kwargs:
                    kwargs['initial'] = {}
                kwargs['initial']['system_type'] = system.id
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                sys_type = form.cleaned_data.get('system_type')
                if sys_type:
                    pk = sys_type.pk if hasattr(sys_type, 'pk') else sys_type
                    if pk in seen:
                        form.add_error('system_type', 'Система указана повторно')
                    seen.add(pk)


ContractSystemCheckFormSet = forms.inlineformset_factory(
    Contract,
    ContractSystemCheck,
    form=ContractSystemCheckForm,
    formset=BaseContractSystemCheckFormSet,
    extra=0,
    can_delete=True,
    min_num=0,
    max_num=200,
)


# ========== ОБЪЕКТЫ ЗАЩИТЫ ==========
# Формы для работы с объектами защиты внутри договора
class ProtectionObjectForm(forms.ModelForm):
    """
    Форма объекта защиты с каскадным выбором региона→района.
    """

    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=False,
        empty_label="— Выберите регион —",
        widget=forms.Select(attrs={
            'class': 'form-select region-select',  # <-- Добавлен класс region-select для удобства
        })
    )

    # Оставляем как атрибут класса, НО НЕ включаем в Meta.fields
    ak_ids = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'class': 'ak-ids-hidden'})
    )

    class Meta:
        model = ProtectionObject
        fields = ['name', 'region', 'district', 'address', 'contacts',
                  'subcontractor', 'total_sum_subcontract', 'monthly_sum_subcontract',
                  ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Главный корпус МБДОУ ДС №1',
            }),
            'district': forms.Select(attrs={
                'class': 'form-select',
                'disabled': 'disabled',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Почтовый адрес объекта...',
            }),
            'contacts': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Контактные данные ответственных лиц...',
            }),
            'subcontractor': forms.Select(attrs={
                'class': 'form-select',
            }),
            'total_sum_subcontract': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'monthly_sum_subcontract': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
        }
        help_texts = {
            'name': 'Укажите название объекта по спецификации договора',
            'district': 'Выберите район после выбора региона',
            'subcontractor': 'Компания-субподрядчик (если применимо)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ВРЕМЕННАЯ ОТЛАДКА (убрать после проверки)
        # print(f"=== POForm init ===")
        # print(f"  prefix: {self.prefix}")
        # print(f"  instance.pk: {self.instance.pk}")
        # print(f"  data region key: {self.add_prefix('region')}")
        # print(f"  data region value: {self.data.get(self.add_prefix('region')) if self.data else 'N/A'}")

        self.fields['subcontractor'].queryset = Company.objects.filter(
            is_subcontractor=True
        ).order_by('name')

        # ============================================================
        # 1. ПРИОРИТЕТ: POST-данные (создание / редактирование / ошибка)
        # ============================================================
        if self.data:
            region_id = self.data.get(self.add_prefix('region'))

            if region_id:
                try:
                    region_id_int = int(region_id)
                    region = Region.objects.get(pk=region_id_int)
                    self.fields['district'].queryset = District.objects.filter(
                        region=region
                    ).order_by('name')
                    self.fields['region'].initial = region_id_int
                    self.fields['district'].widget.attrs.pop('disabled', None)
                except (ValueError, Region.DoesNotExist):
                    self.fields['district'].queryset = District.objects.none()
            else:
                self.fields['district'].queryset = District.objects.none()

            # Восстанавливаем выбранный район из POST (для отображения при ошибке)
            district_id = self.data.get(self.add_prefix('district'))
            if district_id:
                try:
                    self.fields['district'].initial = int(district_id)
                except ValueError:
                    self.fields['district'].initial = district_id

            # Восстанавливаем ak_ids из POST
            raw_ak_ids = self.data.get(self.add_prefix('ak_ids'), '')
            if raw_ak_ids:
                self.fields['ak_ids'].initial = raw_ak_ids

        # ============================================================
        # 2. GET для существующего объекта (instance уже в базе)
        # ============================================================
        elif self.instance.pk and self.instance.district:
            self.fields['region'].initial = self.instance.district.region_id
            self.fields['district'].queryset = District.objects.filter(
                region=self.instance.district.region
            ).order_by('name')
            self.fields['district'].initial = self.instance.district_id
            self.fields['district'].widget.attrs.pop('disabled', None)

            current_ak_ids = list(self.instance.aks.values_list('id', flat=True))
            self.fields['ak_ids'].initial = ','.join(map(str, current_ak_ids))

        # ============================================================
        # 3. Новый объект (чистый GET без данных)
        # ============================================================
        else:
            self.fields['district'].queryset = District.objects.none()

    def clean_ak_ids(self):
        raw = self.cleaned_data.get('ak_ids', '')
        if not raw:
            return []
        try:
            ids = [int(x) for x in raw.split(',') if x.strip()]
            if not ids:
                return []
            existing = set(
                Ak.objects.filter(id__in=ids).values_list('id', flat=True)
            )
            if not existing.issuperset(set(ids)):
                missing = set(ids) - existing
                raise forms.ValidationError(f"АК с ID {missing} не найдены")
            return list(existing)
        except ValueError:
            raise forms.ValidationError("Некорректный формат ID АК")

    # def clean_total_sum_subcontract(self):
    #     val = self.cleaned_data.get('total_sum_subcontract')
    #     if val is not None and val < 0:
    #         raise forms.ValidationError("Сумма не может быть отрицательной")
    #     return val
    #
    # def clean_monthly_sum_subcontract(self):
    #     val = self.cleaned_data.get('monthly_sum_subcontract')
    #     if val is not None and val < 0:
    #         raise forms.ValidationError("Сумма не может быть отрицательной")
    #     return val


class BaseProtectionObjectFormSet(forms.BaseInlineFormSet):
    """
    Проверяем, что в договоре есть хотя бы один неудалённый объект защиты.
    """

    def clean(self):
        super().clean()

        # Если в отдельных формах уже есть ошибки — не мешаем их показу
        if any(self.errors):
            return

        active_count = 0
        for form in self.forms:
            # cleaned_data может отсутствовать, если форма пустая и не валидировалась
            if hasattr(form, 'cleaned_data') and not form.cleaned_data.get('DELETE', False):
                active_count += 1

        if active_count < 1:
            raise forms.ValidationError(
                "Добавьте хотя бы один объект защиты к договору.",
                code='min_protection_objects'
            )


# Formset для объектов защиты
ProtectionObjectFormSet = forms.inlineformset_factory(
    Contract,
    ProtectionObject,
    form=ProtectionObjectForm,
    formset=BaseProtectionObjectFormSet,
    extra=0,  # <-- Изменить с 1 на 0 (HTMX будет добавлять формы динамически)
    can_delete=True,
    min_num=0,
    max_num=50,
)


# ========== ВСПОМОГАТЕЛЬНЫЕ ФОРМЫ ==========
# Поиск АК
class AkSearchForm(forms.Form):
    """Форма поиска АК для добавления к объекту защиты"""

    search_query = forms.CharField(
        label="Поиск АК",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID, номер или название АК...',
            'autocomplete': 'off',
        })
    )
