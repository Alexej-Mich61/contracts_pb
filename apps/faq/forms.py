from django import forms
from .models import FAQItem, FAQFile


class FAQItemForm(forms.ModelForm):
    """Форма для вопроса-ответа."""

    class Meta:
        model = FAQItem
        fields = ["question", "answer", "order", "is_active"]
        widgets = {
            "question": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Введите вопрос"
            }),
            "answer": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Введите ответ"
            }),
            "order": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 0
            }),
        }


class FAQFileForm(forms.ModelForm):
    """Форма для загрузки файла."""

    class Meta:
        model = FAQFile
        fields = ["title", "file", "description"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Название файла (опционально)"
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Краткое описание (опционально)"
            }),
            "file": forms.FileInput(attrs={
                "class": "form-control"
            }),
        }