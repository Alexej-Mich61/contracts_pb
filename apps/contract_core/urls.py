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
    # HTMX эндпоинты для формы договора
    path("contracts/filter/executors/",
         views.FilterExecutorsView.as_view(),
         name="filter_executors"),
    path("contracts/filter/works/",
         views.FilterWorksView.as_view(),
         name="filter_works"),
    path("contracts/search/customers/",
         views.CustomerSearchView.as_view(),
         name="search_customers"),
    path("contracts/filter/dynamic-fields/",
         views.DynamicFieldsView.as_view(),
         name="dynamic_fields"),
    path("contracts/filter/districts-by-region/",
         views.FilterDistrictsByRegionView.as_view(),
         name="filter_districts_by_region"),
    path("contracts/search/ak/",
         views.AkSearchView.as_view(),
         name="search_ak"),

    # Действия с договором
    path("contracts/<int:contract_pk>/systems/<int:system_type_pk>/mark/",
         views.MarkSystemCheckView.as_view(),
         name="mark_system_check"),
    path("contracts/<int:contract_pk>/objects/<int:object_pk>/ak/<int:ak_pk>/add/",
         views.AddAkToObjectView.as_view(),
         name="add_ak_to_object"),
    path("contracts/<int:contract_pk>/objects/<int:object_pk>/ak/<int:ak_pk>/remove/",
         views.RemoveAkFromObjectView.as_view(),
         name="remove_ak_from_object"),


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
    path("reports/subcontractors_to/", views.SubcontractorsToReportsView.as_view(),
         name="subcontractors_to_reports_list"),
    path("reports/signing-stages/", views.ContractSigningStageReportsView.as_view(),
         name="contract_signing_stage_reports"),
    path("reports/signing-stages/excel/", views.ContractSigningStageReportsExcelView.as_view(),
         name="contract_signing_stage_reports_excel"),
    path("reports/works_sum/", views.WorksSumReportView.as_view(), name="works_sum_reports"),
    path("reports/works_sum/excel/", views.WorksSumReportExcelView.as_view(), name="works_sum_reports_excel"),
    # Отчет по статусам и суммам
    path("reports/status_sum/", views.StatusSumReportView.as_view(), name="status_sum_reports"),
    path("reports/status_sum/excel/", views.StatusSumReportExcelView.as_view(), name="status_sum_reports_excel"),

    # Справочники АК
    path("catalogs/ak/", views.AkListView.as_view(), name="ak_list"),
    path("catalogs/ak/add/", views.AkCreateView.as_view(), name="ak_create"),
    path("catalogs/ak/<int:pk>/edit/", views.AkUpdateView.as_view(), name="ak_update"),
    path("catalogs/ak/stats/", views.AkStatsView.as_view(), name="ak_stats"),

    # Справочники Компании
    path("catalogs/companies/", views.CompaniesListView.as_view(), name="companies_list"),
    path("catalogs/companies/add/", views.CompanyCreateView.as_view(), name="company_create"),
    path("catalogs/companies/<int:pk>/update/", views.CompanyUpdateView.as_view(), name="company_update"),
    path("catalogs/companies/stats/", views.CompanyStatsView.as_view(), name="company_stats"),
    path("catalogs/companies/excel/", views.CompaniesListExcelView.as_view(), name="companies_list_excel"),

    # Справочники Стадий подписания контракта
    path(
        "catalogs/signing_stage/",
        views.SigningStageListView.as_view(),
        name="signing_stage_list"
    ),

    # Справочники Работы
    path(
        "catalogs/work/",
        views.WorkListView.as_view(),
        name="work_list"
    ),

    # Справочники Типы Систем
    path(
        "catalogs/system_type/",
        views.SystemTypeListView.as_view(),
        name="system_type_list"
    ),

]
