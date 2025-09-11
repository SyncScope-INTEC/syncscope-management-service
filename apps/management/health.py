import time

import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from config.database_retry import DatabaseHealthCheck, database_retry


@extend_schema(
    tags=["Health"],
    summary="Health check endpoint",
    description="Check the health status of the service including database and cache connections.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "healthy"},
                "timestamp": {"type": "string", "example": "2024-01-01T12:00:00Z"},
                "version": {"type": "string", "example": "1.0.0"},
                "services": {
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "example": "healthy"},
                        "cache": {"type": "string", "example": "healthy"},
                    },
                },
            },
        },
        503: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "unhealthy"},
                "errors": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": getattr(settings, "VERSION", "1.0.0"),
        "services": {},
    }

    errors = []

    # Check database connection with retry logic
    try:
        if DatabaseHealthCheck.is_healthy(use_cache=False):
            health_status["services"]["database"] = "healthy"
        else:
            health_status["services"]["database"] = "unhealthy"
            errors.append("Database: Connection failed after retries")
    except Exception as e:
        health_status["services"]["database"] = "unhealthy"
        errors.append(f"Database: {str(e)}")

    # Check cache/Redis connection with retry logic
    @database_retry(max_retries=2, log_attempts=False)
    def check_cache():
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            return True
        else:
            raise Exception("Unable to read/write cache")

    try:
        if check_cache():
            health_status["services"]["cache"] = "healthy"
    except Exception as e:
        health_status["services"]["cache"] = "unhealthy"
        errors.append(f"Cache: {str(e)}")

    # Determine overall status
    if errors:
        health_status["status"] = "unhealthy"
        health_status["errors"] = errors
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(health_status, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Health"],
    summary="Readiness check endpoint",
    description="Check if the service is ready to accept requests.",
    responses={
        200: {
            "type": "object",
            "properties": {"status": {"type": "string", "example": "ready"}},
        },
        503: {
            "type": "object",
            "properties": {"status": {"type": "string", "example": "not ready"}},
        },
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check endpoint for Kubernetes/Railway deployments.
    """
    try:
        # Database check with retry logic
        if DatabaseHealthCheck.is_healthy(use_cache=True):
            return Response({"status": "ready"}, status=status.HTTP_200_OK)
        else:
            return Response({"status": "not ready"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception:
        return Response({"status": "not ready"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@extend_schema(
    tags=["Health"],
    summary="Liveness check endpoint",
    description="Check if the service is alive (basic endpoint for load balancers).",
    responses={
        200: {
            "type": "object",
            "properties": {"status": {"type": "string", "example": "alive"}},
        }
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def liveness_check(request):
    """
    Simple liveness check - just returns 200 if the service is running.
    This endpoint is used by Railway for health checks and should always be fast.
    """
    try:
        return Response({"status": "alive", "service": "management"}, status=status.HTTP_200_OK)
    except Exception:
        # Even if something goes wrong, try to return a basic response
        from django.http import JsonResponse
        return JsonResponse({"status": "alive", "service": "management"}, status=200)


@csrf_exempt
@require_http_methods(["GET"])
def simple_health_check(request):
    """
    Ultra-simple health check that bypasses all middleware.
    Used as a fallback for deployment health checks.
    """
    return JsonResponse({"status": "ok", "service": "management-service"}, status=200)
