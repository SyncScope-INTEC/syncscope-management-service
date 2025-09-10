"""
Test-specific settings for pytest
Uses SQLite in-memory database for faster, isolated testing
"""

import os

from .settings import *

# Use SQLite for testing to avoid PostgreSQL connection issues
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            "NAME": ":memory:",
        },
    }
}


# Disable migrations for faster testing
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Reduce password hashing time for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable logging during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
    },
}

# Use a simple cache backend
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Disable CSRF for testing
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Set a simple secret key for testing
SECRET_KEY = "test-secret-key-for-testing-only"

# Override auth service URL for testing
AUTH_SERVICE_URL = "http://testserver"

# Test JWT settings
JWT_SECRET_KEY = "test-jwt-secret-key"

# Disable rate limiting for tests
DISABLE_THROTTLING = True

# Test redis settings
REDIS_URL = "redis://localhost:6379/1"

# GitHub test settings
GITHUB_CLIENT_ID = "test-github-client-id"
GITHUB_CLIENT_SECRET = "test-github-client-secret"

# Management service test limits
MAX_TEAM_MEMBERS = 10
MAX_PROJECTS_PER_TEAM = 5
MAX_INTEGRATIONS_PER_PROJECT = 3
GITHUB_SYNC_INTERVAL = 60
DEFAULT_COMMIT_HISTORY_LIMIT = 10

# Configure static files for testing
STATICFILES_DIRS = []
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
