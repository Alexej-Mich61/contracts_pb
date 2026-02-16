# apps/contract_core/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views


app_name = "contract_core"

urlpatterns = [
    # Договоры по типам (объединённый подход)
    path("contracts/oneoff-licensee/", views.ContractOneoffLicenseeView.as_view(),
         name="contract_oneoff_licensee"),
    path("contracts/longterm-licensee/", views.ContractLongtermToLicenseeView.as_view(),
         name="contract_longterm_to_licensee"),
    path("contracts/oneoff-lab/", views.ContractOneoffLabView.as_view(),
         name="contract_oneoff_lab"),

    # Универсальный (общий) список договоров
    path("contracts/", views.ContractListView.as_view(),
         name="contract_list_all"),
    path("contracts/<slug:type_slug>/", views.ContractListView.as_view(),
         name="contract_list_by_type"),

    # История
    path("contracts/history/", views.ContractHistoryView.as_view(), name="contract_history"),

    # Корзина
    path("contracts/trash/", views.ContractTrashView.as_view(), name="contract_trash"),

    # Отчёты
    path("reports/customers/", views.CustomerReportsView.as_view(), name="customer_reports"),
    path("reports/executors/", views.ExecutorReportsView.as_view(), name="executor_reports"),
    path("reports/subcontractors/", views.SubcontractorsReportsView.as_view(),
         name="subcontractors_reports"),

    # Справочники
    path("catalogs/ak/", views.AkListView.as_view(), name="ak_list"),
    path("catalogs/ak/add/", views.AkCreateView.as_view(), name="ak_create"),
    path("catalogs/companies/", views.CompaniesListView.as_view(), name="companies_list"),
    path("catalogs/companies/add/", views.CompanyCreateView.as_view(), name="company_create"),
    path("catalogs/companies/<int:pk>/update/", views.CompanyUpdateView.as_view(), name="company_update"),
]
