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


# ========== СПРАВОЧНИКИ ==========
# Формы для управления справочными данными (АК, Компании)

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
            'note', 'file', 'total_sum', 'monthly_sum', 'advance'
        ]
        widgets = {
            'type': forms.Select(attrs={
                'class': 'form-select',
                'hx-get': '',
                'hx-target': '#dynamic-fields-container',
                'hx-trigger': 'change',
                'hx-include': '[name="csrfmiddlewaretoken"]',
                'hx-swap': 'innerHTML',
            }),
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 45/2024',
            }),
            'date_concluded': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'customer': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_customer',  # Важно для таргета HTMX
            }),
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
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        # Устанавливаем дефолтные значения для новых договоров
        if not self.instance.pk:
            today = timezone.now().date()
            self.fields['date_concluded'].initial = today
            self.fields['date_start'].initial = today

            # При создании — пустой queryset для customer ТОЛЬКО если GET запрос (первая загрузка)
            # При POST запросе нужен полный queryset для валидации
            if not self.data:
                self.fields['customer'].queryset = Company.objects.none()
                self.fields['customer'].choices = [('', '— Введите название или ИНН и нажмите "Найти" —')]
                self.fields['executor'].queryset = Company.objects.none()
                self.fields['work'].queryset = Work.objects.none()
            else:
                # POST запрос — даем полный queryset для валидации
                self.fields['customer'].queryset = Company.objects.filter(is_customer=True)
                self.fields['executor'].queryset = Company.objects.filter(
                    Q(is_licensee=True) | Q(is_laboratory=True)
                )
                self.fields['work'].queryset = Work.objects.filter(is_active=True)
        else:
            # При редактировании — показываем только текущего заказчика (как у вас было)
            if self.instance.customer:
                self.fields['customer'].queryset = Company.objects.filter(pk=self.instance.customer.pk)
                self.fields['customer'].initial = self.instance.customer_id
            else:
                self.fields['customer'].queryset = Company.objects.none()
                self.fields['customer'].choices = [('', '— Выберите заказчика —')]

            # Исполнитель и работа
            self.fields['executor'].queryset = Company.objects.filter(
                Q(is_licensee=True) | Q(is_laboratory=True)
            ).distinct().order_by('name')
            self.fields['work'].queryset = Work.objects.filter(is_active=True)
            self.fields['executor'].initial = self.instance.executor_id
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
            # 'hx-get': '',  # <-- Удалить или закомментировать (URL задается в шаблоне)
            # 'hx-target': 'closest .district-wrapper',
            # 'hx-trigger': 'change',
            # 'hx-swap': 'innerHTML',
            # 'hx-select': '#district-field-wrapper',
        })
    )

    # region = forms.ModelChoiceField(
    #     queryset=Region.objects.all(),
    #     required=False,
    #     empty_label="— Выберите регион —",
    #     widget=forms.Select(attrs={
    #         'class': 'form-select',
    #         'hx-get': '',  # URL для загрузки районов
    #         'hx-target': 'closest .district-wrapper',
    #         'hx-trigger': 'change',
    #         'hx-swap': 'innerHTML',
    #         'hx-select': '#district-field-wrapper',
    #     })
    # )


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
    extra=0,  # <-- Изменить с 1 на 0 (HTMX будет добавлять формы динамически)
    can_delete=True,
    min_num=0,
    max_num=50,
)


# ========== ВСПОМОГАТЕЛЬНЫЕ ФОРМЫ ==========

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
