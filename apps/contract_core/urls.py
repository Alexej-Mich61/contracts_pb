#apps/contract_core/urls.py
from django.urls import path
from . import views

app_name = "contract"

urlpatterns = [
    path("", views.ContractListView.as_view(), name="list"),
    path("create/", views.ContractCreateView.as_view(), name="create"),
    path("<int:pk>/change/", views.ContractUpdateView.as_view(), name="update"),
]