"""
URL configuration for syncscope-management-service project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.management.views import api_home
from apps.management.health import health_check, readiness_check, liveness_check

urlpatterns = [
    # Home page
    path("", api_home, name="api_home"),
    path("admin/", admin.site.urls),
    # Health check endpoints
    path("health/", health_check, name="health_check"),
    path("health/ready/", readiness_check, name="readiness_check"),
    path("health/live/", liveness_check, name="liveness_check"),
    # Management endpoints
    path("management/", include("apps.management.urls")),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
