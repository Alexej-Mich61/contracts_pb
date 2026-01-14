#apps/contract_core/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from apps.identity.models import User   # своя модель, чтобы PyCharm видел поля
from .forms import DynamicContractForm


class ContractListView(LoginRequiredMixin, ListView):
    """Список договоров текущего пользователя."""
    model               = None                      # определим ниже
    template_name       = "contracts/list.html"
    context_object_name = "contracts"

    def get_queryset(self):
        user: User = self.request.user              # type-hint для PyCharm
        # показываем только те договоры, где пользователь – исполнитель
        return user.companies.all()

    def get_context_data(self, **kwargs):
        """Подгружаем сами объекты Contract через related_name."""
        context = super().get_context_data(**kwargs)
        # фильтруем Contract по исполнителю
        context["contracts"] = (
            self.get_queryset()
            .prefetch_related("contractcore_set")
            .order_by("-created_at")
        )
        return context


class ContractCreateView(LoginRequiredMixin, CreateView):
    """Создание нового договора."""
    def get_model(self):
        from .models import Contract                  # импорт внутри метода
        return Contract

    form_class      = DynamicContractForm
    template_name   = "contracts/form.html"
    success_url     = reverse_lazy("contract:list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        kw["initial"] = {"type": self.request.GET.get("type")}
        return kw


class ContractUpdateView(LoginRequiredMixin, UpdateView):
    """Редактирование существующего договора."""
    def get_model(self):
        from .models import Contract                  # импорт внутри метода
        return Contract

    form_class      = DynamicContractForm
    template_name   = "contracts/form.html"
    success_url     = reverse_lazy("contract:list")

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw
