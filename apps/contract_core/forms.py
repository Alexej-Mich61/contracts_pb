#apps/contract_core/forms.py
from django import forms
from apps.contract_works.models import Work
from .models import Contract


class DynamicContractForm(forms.ModelForm):
    """Основные поля + работы (без блоков)."""

    works = forms.ModelMultipleChoiceField(
        queryset=Work.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Виды работ",
    )

    class Meta:
        model = Contract
        fields = [
            "type",
            "number",
            "date_concluded",
            "customer",
            "inn",
            "date_start",
            "date_end",
            "executor",
            "note",
            "total_sum",
            "monthly_sum",
            "advance",
            "status",
            "final_act_date",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["executor"].queryset = user.companies.all()

        ct_type = self.initial.get("type") or self.data.get("type")
        if ct_type:
            self.fields["type"].initial = ct_type
            self._filter_works(ct_type)

    def _filter_works(self, ct_type):
        company_kind, contract_type = ct_type.split("_", 1)
        qs = Work.objects.filter(work_type=ct_type, company_kind=company_kind)
        self.fields["works"].queryset = qs

    def save(self, commit=True):
        contract = super().save(commit=False)
        contract.creator = self.user
        if commit:
            contract.save()
            self._save_works(contract)
        return contract

    def _save_works(self, contract):
        contract.works.set(self.cleaned_data["works"])