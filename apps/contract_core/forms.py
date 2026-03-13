# apps/contract_core/forms.py
from django import forms
from django.db.models import Q
from django.core.validators import FileExtensionValidator
from django.utils import timezone

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
from .validators import file_validator

# форма АК
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
    class Meta:
        model = Company
        fields = [
            'name', 'inn', 'fias_code',
            'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor',
            'notification_agreed'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'inn': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
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



# форма контракта
class ContractForm(forms.ModelForm):
    """Форма договора с динамической фильтрацией через HTMX"""

    # Кастомное поле для поиска заказчика (autocomplete)
    customer_search = forms.CharField(
        label="Поиск заказчика",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите название или ИНН...',
            'hx-get': '',  # URL будет подставлен в шаблоне
            'hx-trigger': 'keyup changed delay:300ms, search',
            'hx-target': '#customer-search-results',
            'hx-indicator': '.customer-search-indicator',
            'autocomplete': 'off',
        }),
        help_text="Начните вводить название или ИНН компании-заказчика"
    )

    class Meta:
        model = Contract
        fields = [
            'type', 'number', 'date_concluded',
            'customer', 'date_start', 'date_end', 'executor', 'work',
            'note', 'file', 'total_sum', 'monthly_sum', 'advance'
        ]
        widgets = {
            'type': forms.Select(attrs={
                'class': 'form-select',
                'hx-get': '',  # URL для обновления работ и исполнителей
                'hx-target': '#dynamic-fields-container',
                'hx-trigger': 'change',
                'hx-include': '[name="csrfmiddlewaretoken"]',
            }),
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 45/2024',
            }),
            'date_concluded': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'customer': forms.HiddenInput(),  # Скрытое поле для ID выбранной компании
            'date_start': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'date_end': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'executor': forms.Select(attrs={
                'class': 'form-select',
                'disabled': 'disabled',  # Активируется через HTMX после выбора типа
            }),
            'work': forms.Select(attrs={
                'class': 'form-select',
                'disabled': 'disabled',  # Активируется через HTMX после выбора типа
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
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        # Устанавливаем дефолтные значения для новых договоров
        if not self.instance.pk:
            self.fields['date_concluded'].initial = timezone.now().date()
            self.fields['date_start'].initial = timezone.now().date()

        # Начальное состояние: пустые queryset для зависимых полей
        # Они заполнятся через HTMX после выбора типа договора
        self.fields['executor'].queryset = Company.objects.none()
        self.fields['work'].queryset = Work.objects.none()

        # Если редактирование или есть initial данные — заполняем
        contract_type = self.data.get('type') or self.initial.get('type')
        if contract_type or self.instance.pk:
            self._setup_dynamic_fields(contract_type)

        # Если есть выбранный заказчик — показываем его название в поиске
        if self.instance.customer_id:
            self.fields['customer_search'].initial = str(self.instance.customer)

    def _setup_dynamic_fields(self, contract_type):
        """Настройка полей в зависимости от типа договора"""
        if not contract_type and self.instance.pk:
            contract_type = self.instance.type

        if not contract_type:
            return

        # Активируем поля
        self.fields['executor'].widget.attrs.pop('disabled', None)
        self.fields['work'].widget.attrs.pop('disabled', None)

        # Фильтруем исполнителей
        self.fields['executor'].queryset = self._get_executor_queryset(contract_type)

        # Фильтруем работы
        work_type_map = {
            'oneoff_licensee': 'work_oneoff_licensee',
            'longterm_to_licensee': 'work_longterm_to_licensee',
            'oneoff_lab': 'work_oneoff_lab',
        }
        work_type = work_type_map.get(contract_type)
        if work_type:
            self.fields['work'].queryset = Work.objects.filter(
                work_type=work_type,
                is_active=True
            )

        # Если редактирование — устанавливаем текущие значения
        if self.instance.pk:
            self.fields['executor'].initial = self.instance.executor_id
            self.fields['work'].initial = self.instance.work_id

    def _get_executor_queryset(self, contract_type):
        """
        Фильтрация исполнителей:
        1. Компании, где пользователь — сотрудник
        2. + Фильтр по типу договора (is_licensee / is_laboratory)
        """
        # Базовый фильтр — компании пользователя
        user_companies = Company.objects.filter(
            employees__user=self.user,
            employees__is_active=True
        ).values_list('id', flat=True)

        # Дополнительный фильтр по типу договора
        type_filter = Q()
        if contract_type in ['oneoff_licensee', 'longterm_to_licensee']:
            type_filter |= Q(is_licensee=True)
        if contract_type == 'oneoff_lab':
            type_filter |= Q(is_laboratory=True)

        # Объединяем: компании пользователя ИЛИ подходящие по типу
        # Исключаем дубли через distinct()
        return Company.objects.filter(
            (Q(id__in=user_companies) | type_filter) &
            (Q(is_licensee=True) | Q(is_laboratory=True))
        ).distinct().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get('customer')

        if not customer:
            self.add_error('customer_search', 'Необходимо выбрать заказчика из списка найденных')

        # Валидация дат
        date_start = cleaned_data.get('date_start')
        date_end = cleaned_data.get('date_end')

        if date_start and date_end and date_end < date_start:
            self.add_error('date_end', 'Дата окончания не может быть раньше даты начала')

        return cleaned_data


class ContractSigningStageForm(forms.ModelForm):
    """Форма стадии подписания договора"""

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


class ContractSystemCheckForm(forms.ModelForm):
    """Форма для отметки проверки системы (используется в шаблоне с кнопкой)"""

    class Meta:
        model = ContractSystemCheck
        fields = ['note']
        widgets = {
            'note': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Примечание (необязательно)',
                'maxlength': 200,
            }),
        }
        labels = {
            'note': '',
        }


class FinalActForm(forms.ModelForm):
    """Форма итогового акта"""

    class Meta:
        model = FinalAct
        fields = ['present', 'date', 'file', 'note']
        widgets = {
            'present': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
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
        help_texts = {
            'present': 'Отметьте, если итоговый акт сформирован',
            'file': 'Скан подписанного акта',
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
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
        }
        labels = {
            'title': 'Название',
            'date': 'Дата',
            'file': 'Файл',
        }


# Formset для промежуточных актов
InterimActFormSet = forms.inlineformset_factory(
    Contract,
    InterimAct,
    form=InterimActForm,
    extra=1,
    can_delete=True,
    min_num=0,
    max_num=20,
)


class ProtectionObjectForm(forms.ModelForm):
    """Форма объекта защиты с каскадным выбором региона→района"""

    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        required=False,
        empty_label="— Выберите регион —",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'hx-get': '',  # URL для загрузки районов
            'hx-target': 'closest .district-wrapper',
            'hx-trigger': 'change',
            'hx-swap': 'innerHTML',
            'hx-select': '#district-field-wrapper',
        })
    )

    class Meta:
        model = ProtectionObject
        fields = ['name', 'region', 'district', 'address', 'contacts',
                  'subcontractor', 'total_sum_subcontract', 'monthly_sum_subcontract']
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

        self.fields['subcontractor'].queryset = Company.objects.filter(
            is_subcontractor=True
        ).order_by('name')

        if self.instance.pk and self.instance.district:
            self.fields['region'].initial = self.instance.district.region
            self.fields['district'].queryset = District.objects.filter(
                region=self.instance.district.region
            )
            self.fields['district'].widget.attrs.pop('disabled', None)
        else:
            self.fields['district'].queryset = District.objects.none()


# Formset для объектов защиты
ProtectionObjectFormSet = forms.inlineformset_factory(
    Contract,
    ProtectionObject,
    form=ProtectionObjectForm,
    extra=1,
    can_delete=True,
    min_num=0,
    max_num=50,
)


class AkSearchForm(forms.Form):
    """Форма поиска АК для добавления к объекту защиты"""

    search_query = forms.CharField(
        label="Поиск АК",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID, номер или название АК...',
            'hx-get': '',  # URL поиска
            'hx-trigger': 'keyup changed delay:400ms',
            'hx-target': '#ak-search-results',
            'autocomplete': 'off',
        })
    )


