from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

class ContractOneoffLicenseeView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_oneoff_licensee.html"

class ContractLongtermToLicenseeView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_longterm_to_licensee.html"

class ContractOneoffLabView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_oneoff_lab.html"

class ContractHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_history.html"

class ContractTrashView(LoginRequiredMixin, TemplateView):
    template_name = "contracts/contract_trash.html"

class CustomerReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/customer_repots.html"

class ExecutorReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/executor_reports.html"

class SubcontractorsReportsView(LoginRequiredMixin, TemplateView):
    template_name = "reports/subcontractors_reports.html"

class AkListView(LoginRequiredMixin, TemplateView):
    template_name = "catalogs/ak_list.html"

class CompaniesListView(LoginRequiredMixin, TemplateView):
    template_name = "catalogs/companies_list.html"

class UsersListView(LoginRequiredMixin, TemplateView):
    template_name = "catalogs/users_list.html"

class ChatView(LoginRequiredMixin, TemplateView):
    template_name = "chat/chat.html"

class FAQView(LoginRequiredMixin, TemplateView):
    template_name = "FAQ.html"
