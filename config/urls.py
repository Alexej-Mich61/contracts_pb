#config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView  # ← новый импорт
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.contract_core.urls")),
    path("auth/", include("apps.identity.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns