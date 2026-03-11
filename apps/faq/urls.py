# apps/faq/urls.py
from django.urls import path
from . import views

app_name = "faq"

urlpatterns = [
    path("", views.FAQListView.as_view(), name="list"),
    path("item/create/", views.FAQItemCreateView.as_view(), name="item_create"),
    path("item/<int:pk>/", views.FAQItemDetailView.as_view(), name="item_detail"),
    path("item/<int:pk>/edit/", views.FAQItemUpdateView.as_view(), name="item_edit"),
    path("item/<int:pk>/delete/", views.FAQItemDeleteView.as_view(), name="item_delete"),
    path("file/upload/", views.FAQFileUploadView.as_view(), name="file_upload"),
    path("file/<int:pk>/download/", views.FAQFileDownloadView.as_view(), name="file_download"),
    path("file/<int:pk>/delete/", views.FAQFileDeleteView.as_view(), name="file_delete"),
]