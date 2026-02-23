# apps/contract_core/forms.py
from django import forms
from .models import Ak, District, Company, Work, Contract
from django.db.models import Q


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



class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'inn', 'fias_code', 'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'inn': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'fias_code': forms.TextInput(attrs={'class': 'form-control'}),
            'is_customer': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_licensee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_laboratory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_subcontractor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'type', 'number', 'date_concluded',
            'customer', 'date_start', 'date_end', 'executor', 'work',
            'note', 'file', 'total_sum', 'monthly_sum', 'advance'
        ]
        widgets = {
            'date_concluded': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'note': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Company.objects.filter(is_customer=True)
        self.fields['executor'].queryset = Company.objects.filter(
            Q(is_licensee=True) | Q(is_laboratory=True)
        )
        self.fields['work'].queryset = Work.objects.filter(is_active=True)


