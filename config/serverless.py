"""
Serverless-specific configuration and utilities
"""

import logging
import os
from datetime import timedelta

from django.conf import settings

from config.database_retry import configure_connection_pool

logger = logging.getLogger(__name__)


def setup_serverless_environment():
    """Configure Django for serverless environment"""

    # Configure database connection pool
    configure_connection_pool()

    # Set shorter timeouts for serverless
    settings.REST_FRAMEWORK.update(
        {
            "DEFAULT_TIMEOUT": 30,  # 30 seconds max for API calls
        }
    )

    # Configure JWT for shorter-lived tokens in serverless
    if hasattr(settings, "SIMPLE_JWT"):
        settings.SIMPLE_JWT.update(
            {
                "ACCESS_TOKEN_LIFETIME": timedelta(
                    minutes=15
                ),  # Shorter for serverless
                "REFRESH_TOKEN_LIFETIME": timedelta(hours=1),  # Shorter refresh window
            }
        )

    # Disable debug toolbar in serverless
    if "debug_toolbar" in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS.remove("debug_toolbar")

    # Configure logging for serverless
    if not settings.DEBUG:
        settings.LOGGING["handlers"]["console"]["level"] = "WARNING"

    logger.info("✓ Serverless environment configured")


def validate_serverless_config():
    """Validate configuration for serverless deployment"""
    issues = []

    # Check database configuration
    db_config = settings.DATABASES["default"]
    if db_config.get("CONN_MAX_AGE", 0) > 0:
        issues.append("CONN_MAX_AGE should be 0 for serverless")

    # Check Redis configuration
    if "redis" not in settings.CACHES["default"]["LOCATION"].lower():
        issues.append("Redis cache is recommended for serverless")

    # Check secret key
    if settings.SECRET_KEY == "django-insecure-change-me-in-production":
        issues.append("SECRET_KEY should be changed for production")

    # Check debug mode
    if settings.DEBUG and os.environ.get("RAILWAY_ENVIRONMENT") == "production":
        issues.append("DEBUG should be False in production")

    if issues:
        logger.warning(f"Serverless configuration issues: {issues}")
        return False, issues

    logger.info("✓ Serverless configuration validated")
    return True, []


def get_serverless_metrics():
    """Get metrics useful for serverless monitoring"""
    from django.core.cache import cache
    from django.db import connection

    metrics = {
        "database_queries": len(connection.queries),
        "database_vendor": connection.vendor,
    }

    try:
        # Test cache performance
        import time

        start = time.time()
        cache.set("metrics_test", "value", 1)
        cache.get("metrics_test")
        metrics["cache_latency_ms"] = round((time.time() - start) * 1000, 2)
    except Exception:
        metrics["cache_latency_ms"] = None

    return metrics


# Auto-configure if imported
if os.environ.get("SERVERLESS_ENV") == "true":
    setup_serverless_environment()
