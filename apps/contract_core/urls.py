#apps/contract_core/urls.py
from django.urls import path
from . import views

app_name = "contract"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("oneoff-licensee/", views.OneOffLicenseeListView.as_view(), name="oneoff_licensee_list"),
    path("longterm-licensee/", views.LongTermLicenseeListView.as_view(), name="longterm_licensee_list"),
    path("oneoff-lab/", views.OneOffLabListView.as_view(), name="oneoff_lab_list"),
    path("ajax/toggle-system/<int:pk>/<str:field>/", views.toggle_system_check, name="toggle_system"),
    path("ajax/toggle-stage/<int:pk>/<str:field>/", views.toggle_stage_check, name="toggle_stage"),
]