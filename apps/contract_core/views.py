# apps/contract_core/views.py
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from .models import Contract
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404


class IndexView(TemplateView):
    template_name = "contract_core/index.html"

class BaseContractListView(LoginRequiredMixin, ListView):
    paginate_by = 10
    template_name = "contract_core/contract_list.html"
    context_object_name = "contracts"

    def get_queryset(self):
        qs = super().get_queryset().for_user(self.request.user)
        type_filter = self.get_type_filter()
        return qs.filter(type=type_filter, is_trash=False, is_archived=False).select_related("customer", "executor").prefetch_related("objects__district", "objects__aks", "interim_acts")

    def get_type_filter(self):
        return None   # переопределить

class OneOffLicenseeListView(BaseContractListView):
    model = Contract          # ← вместо queryset = Contract.objects.all()
    def get_type_filter(self):
        return Contract.TYPE_ONEOFF_LICENSEE

class LongTermLicenseeListView(BaseContractListView):
    model = Contract
    def get_type_filter(self):
        return Contract.TYPE_LONGTERM_TO_LICENSEE

class OneOffLabListView(BaseContractListView):
    model = Contract
    def get_type_filter(self):
        return Contract.TYPE_ONEOFF_LAB

# ---------- AJAX-переключение чек-боксов ----------

@require_POST
def toggle_system_check(request, pk, field):
    contract = get_object_or_404(Contract, pk=pk)
    if field not in ("gos_services", "oko", "spolokh"):
        return HttpResponse("Bad field", status=400)
    setattr(contract, field, not getattr(contract, field))
    contract.save(update_fields=[field])
    return HttpResponse("")

@require_POST
def toggle_stage_check(request, pk, field):
    contract = get_object_or_404(Contract, pk=pk)
    if field not in ("contract_to_be_signed", "contract_signed", "contract_signed_in_trading_platform",
                     "contract_signed_in_EDO", "contract_original_received", "contract_termination"):
        return HttpResponse("Bad field", status=400)
    # сброс всех стадий, затем установка одной
    for f in ("contract_to_be_signed", "contract_signed", "contract_signed_in_trading_platform",
              "contract_signed_in_EDO", "contract_original_received", "contract_termination"):
        setattr(contract, f, False)
    setattr(contract, field, True)
    contract.save(update_fields=[field])
    return HttpResponse("")



