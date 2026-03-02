# apps/contract_core/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views


app_name = "contract_core"

urlpatterns = [
    # Договоры (объединённый подход)
    # Список договоров (главная страница)
    path("contracts/", views.ContractListView.as_view(), name="contract_list"),

    # HTMX эндпоинты
    path("contracts/filter/", views.ContractListHtmxView.as_view(), name="contract_list_htmx"),
    path("contracts/filter/works/", views.FilterWorksView.as_view(), name="filter_works"),
    path("contracts/filter/districts/", views.FilterDistrictsView.as_view(), name="filter_districts"),


    # Форма создания/редактирования (отдельная страница)
    path("contracts/add/", views.ContractCreateView.as_view(), name="contract_create"),
    path("contracts/<int:pk>/edit/", views.ContractUpdateView.as_view(), name="contract_update"),

    # HTMX эндпоинты для модальных окон
    path("contracts/<int:pk>/detail/", views.ContractDetailHtmxView.as_view(), name="contract_detail_htmx"),
    path("contracts/<int:pk>/history/", views.ContractHistoryHtmxView.as_view(), name="contract_history_htmx"),


    # Корзина
    path("contracts/trash/", views.ContractTrashView.as_view(), name="contract_trash"),

    # Отчёты
    path("reports/customers/", views.CustomerReportsView.as_view(), name="customer_reports"),
    path("reports/executors/", views.ExecutorReportsView.as_view(), name="executor_reports"),
    path("reports/subcontractors/", views.SubcontractorsReportsView.as_view(),
         name="subcontractors_reports"),

    # Справочники АК
    path("catalogs/ak/", views.AkListView.as_view(), name="ak_list"),
    path("catalogs/ak/add/", views.AkCreateView.as_view(), name="ak_create"),
    path("catalogs/ak/<int:pk>/edit/", views.AkUpdateView.as_view(), name="ak_update"),

    # Справочники Компании
    path("catalogs/companies/", views.CompaniesListView.as_view(), name="companies_list"),
    path("catalogs/companies/add/", views.CompanyCreateView.as_view(), name="company_create"),
    path("catalogs/companies/<int:pk>/update/", views.CompanyUpdateView.as_view(), name="company_update"),
]
