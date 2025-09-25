"""
URL configuration for syncscope-management-service project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.management.health import health_check, liveness_check, readiness_check, simple_health_check
from apps.management.views import api_get_team_members, api_home, favicon_view

urlpatterns = [
    # Home page
    path("", api_home, name="api_home"),
    # Favicon
    path("favicon.ico", favicon_view, name="favicon"),
    path("admin/", admin.site.urls),
    # Health check endpoints
    path("health/", simple_health_check, name="health_check"),  # Ultra-simple health check for Railway
    path("health/detailed/", health_check, name="detailed_health_check"),
    path("health/ready/", readiness_check, name="readiness_check"),
    path("health/live/", liveness_check, name="liveness_check"),
    # Management endpoints
    path("management/", include("apps.management.urls")),
    # API endpoints for analytics service integration
    path("api/teams/<str:team_id>/members", api_get_team_members, name="api_team_members"),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
