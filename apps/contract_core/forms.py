# apps/contract_core/forms.py
from django import forms
from .models import Ak, Company, District


class AkForm(forms.ModelForm):
    class Meta:
        model = Ak
        fields = ['number', 'name', 'address', 'district']
        widgets = {
            'district': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['district'].queryset = District.objects.select_related('region').order_by('region__name', 'name')


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'inn', 'fias_code', 'is_customer', 'is_licensee', 'is_laboratory', 'is_subcontractor']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'inn': forms.TextInput(attrs={'class': 'form-control'}),
            'fias_code': forms.TextInput(attrs={'class': 'form-control'}),
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

