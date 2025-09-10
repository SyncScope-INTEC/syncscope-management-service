"""
Database retry and resilience utilities for serverless environments
"""

import logging
import time
from functools import wraps

import psycopg2
from django.core.cache import cache
from django.db import connection, transaction
from django.db.utils import DatabaseError, InterfaceError, OperationalError

logger = logging.getLogger(__name__)


class DatabaseRetryConfig:
    MAX_RETRIES = 3
    INITIAL_DELAY = 0.5  # seconds
    MAX_DELAY = 5.0  # seconds
    BACKOFF_MULTIPLIER = 2

    # Errors that should trigger a retry
    RETRYABLE_ERRORS = (
        OperationalError,
        InterfaceError,
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
        psycopg2.DatabaseError,
        ConnectionError,
    )


def exponential_backoff(attempt):
    """Calculate exponential backoff delay"""
    delay = DatabaseRetryConfig.INITIAL_DELAY * (DatabaseRetryConfig.BACKOFF_MULTIPLIER**attempt)
    return min(delay, DatabaseRetryConfig.MAX_DELAY)


def is_retryable_error(error):
    """Check if an error should trigger a retry"""
    if isinstance(error, DatabaseRetryConfig.RETRYABLE_ERRORS):
        return True

    # Check for specific error messages that indicate temporary issues
    error_msg = str(error).lower()
    retryable_messages = [
        "connection refused",
        "connection timeout",
        "connection reset",
        "connection closed",
        "connection lost",
        "server closed the connection",
        "database is starting up",
        "too many connections",
        "connection pool exhausted",
        "connection not available",
        "timeout expired",
    ]

    return any(msg in error_msg for msg in retryable_messages)


def close_old_connections():
    """Force close old database connections"""
    try:
        connection.close()
        logger.info("Closed old database connection")
    except Exception as e:
        logger.warning(f"Error closing connection: {e}")


def database_retry(max_retries=None, log_attempts=True):
    """Decorator to add database retry logic to functions"""
    if max_retries is None:
        max_retries = DatabaseRetryConfig.MAX_RETRIES

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    # Close old connections before retry
                    if attempt > 0:
                        close_old_connections()

                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if not is_retryable_error(e) or attempt == max_retries:
                        if log_attempts:
                            logger.error(f"Database operation failed after {attempt + 1} attempts: {e}")
                        raise e

                    delay = exponential_backoff(attempt)

                    if log_attempts:
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


class DatabaseHealthCheck:
    """Database health monitoring for serverless environments"""

    HEALTH_CACHE_KEY = "db_health_status"
    HEALTH_CACHE_TIMEOUT = 30  # seconds

    @staticmethod
    @database_retry(max_retries=2, log_attempts=False)
    def check_connection():
        """Check database connection health"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False

    @classmethod
    def is_healthy(cls, use_cache=True):
        """Check if database is healthy with optional caching"""
        if use_cache:
            cached_status = cache.get(cls.HEALTH_CACHE_KEY)
            if cached_status is not None:
                return cached_status

        is_healthy = cls.check_connection()

        if use_cache:
            cache.set(cls.HEALTH_CACHE_KEY, is_healthy, cls.HEALTH_CACHE_TIMEOUT)

        return is_healthy

    @classmethod
    def mark_unhealthy(cls):
        """Mark database as unhealthy in cache"""
        cache.set(cls.HEALTH_CACHE_KEY, False, cls.HEALTH_CACHE_TIMEOUT)


def get_db_with_retry():
    """Get database connection with retry logic"""

    @database_retry()
    def _get_connection():
        # Test the connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return connection

    return _get_connection()


class RetryableQuerySet:
    """Wrapper for QuerySet operations with retry logic"""

    def __init__(self, queryset):
        self.queryset = queryset

    @database_retry()
    def get(self, *args, **kwargs):
        return self.queryset.get(*args, **kwargs)

    @database_retry()
    def filter(self, *args, **kwargs):
        return self.queryset.filter(*args, **kwargs)

    @database_retry()
    def create(self, *args, **kwargs):
        return self.queryset.create(*args, **kwargs)

    @database_retry()
    def update(self, *args, **kwargs):
        return self.queryset.update(*args, **kwargs)

    @database_retry()
    def delete(self, *args, **kwargs):
        return self.queryset.delete(*args, **kwargs)

    @database_retry()
    def exists(self):
        return self.queryset.exists()

    @database_retry()
    def count(self):
        return self.queryset.count()


def atomic_with_retry(using=None, savepoint=True):
    """Transaction decorator with retry logic"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            @database_retry()
            def _atomic_operation():
                with transaction.atomic(using=using, savepoint=savepoint):
                    return func(*args, **kwargs)

            return _atomic_operation()

        return wrapper

    return decorator


# Connection pool settings for serverless
def configure_connection_pool():
    """Configure database connection pool for serverless"""
    from django.conf import settings

    # Update database settings for serverless
    db_config = settings.DATABASES["default"]

    # Connection pool settings
    db_config.setdefault("CONN_MAX_AGE", 0)  # Don't persist connections
    db_config.setdefault("CONN_HEALTH_CHECKS", True)

    # Add connection options for reliability
    if "OPTIONS" not in db_config:
        db_config["OPTIONS"] = {}

    db_config["OPTIONS"].update(
        {
            "connect_timeout": 10,
            "application_name": "syncscope-auth-serverless",
            "options": "-c search_path=auth -c statement_timeout=30000",
        }
    )

    logger.info("Database configured for serverless environment")
