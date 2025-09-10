"""
API-based authentication backend that uses the SyncScope Auth Service.
"""

import logging
import time

import requests
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AuthServiceAPIBackend(BaseBackend):
    """
    Authentication backend that uses the SyncScope Auth Service API.
    Handles cold starts and provides proper service separation.
    """

    def __init__(self):
        self.auth_service_url = settings.AUTH_SERVICE_URL

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate user via the Auth Service API.
        """
        logger.info(f"AuthServiceAPIBackend: Attempting authentication for user: {username}")

        if username is None or password is None:
            logger.warning("AuthServiceAPIBackend: Username or password is None")
            return None

        try:
            # Authenticate with the auth service
            auth_response = self._authenticate_with_service(username, password)

            if auth_response and auth_response.get("user"):
                user_data = auth_response["user"]
                logger.info(f"AuthServiceAPIBackend: Authentication successful for: {username}")

                # Check if user has admin privileges
                role = user_data.get("role", "developer")
                is_staff = user_data.get("is_staff", False) or role in ["admin", "supervisor"]
                is_superuser = user_data.get("is_superuser", False) or role == "admin"

                if user_data.get("is_active", True) and is_staff:
                    logger.info(f"AuthServiceAPIBackend: User {username} has admin privileges (role: {role})")

                    # Create or update local Django user for admin interface
                    user = self._get_or_create_local_user(user_data)
                    logger.info(f"AuthServiceAPIBackend: Created/updated local user: {user}")
                    return user
                else:
                    logger.warning(f"AuthServiceAPIBackend: User {username} does not have admin privileges")
            else:
                logger.warning(f"AuthServiceAPIBackend: Authentication failed for: {username}")

        except Exception as e:
            logger.error(f"AuthServiceAPIBackend: Error during authentication: {str(e)}", exc_info=True)

        return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _authenticate_with_service(self, email, password, max_retries=3):
        """
        Authenticate with the auth service, handling cold starts with retries.
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"AuthServiceAPIBackend: API call attempt {attempt + 1}/{max_retries}")

                response = requests.post(
                    f"{self.auth_service_url}/auth/login/",
                    json={"email": email, "password": password},
                    headers={"Content-Type": "application/json"},
                    timeout=30,  # Longer timeout for cold starts
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in [401, 403]:
                    # Authentication failed - don't retry
                    logger.warning(f"AuthServiceAPIBackend: Authentication failed with status {response.status_code}")
                    return None
                else:
                    logger.warning(f"AuthServiceAPIBackend: API call failed with status {response.status_code}")

            except requests.exceptions.Timeout:
                logger.warning(f"AuthServiceAPIBackend: Timeout on attempt {attempt + 1} (cold start?)")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
            except requests.exceptions.RequestException as e:
                logger.warning(f"AuthServiceAPIBackend: Request failed on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief wait before retry

        logger.error(f"AuthServiceAPIBackend: All {max_retries} attempts failed")
        return None

    def _get_or_create_local_user(self, user_data):
        """
        Create or update a local Django user for admin interface.
        """
        try:
            email = user_data["email"]
            role = user_data.get("role", "developer")

            # Create or update local user
            user, created = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": user_data.get("first_name", ""),
                    "last_name": user_data.get("last_name", ""),
                    "is_staff": user_data.get("is_staff", False) or role in ["admin", "supervisor"],
                    "is_superuser": user_data.get("is_superuser", False) or role == "admin",
                    "is_active": user_data.get("is_active", True),
                },
            )

            if not created:
                # Update existing user info to sync with auth service
                user.email = email
                user.first_name = user_data.get("first_name", "")
                user.last_name = user_data.get("last_name", "")
                user.is_staff = user_data.get("is_staff", False) or role in ["admin", "supervisor"]
                user.is_superuser = user_data.get("is_superuser", False) or role == "admin"
                user.is_active = user_data.get("is_active", True)
                user.save()
                logger.info(f"AuthServiceAPIBackend: Updated existing local user: {user.email}")
            else:
                logger.info(f"AuthServiceAPIBackend: Created new local user: {user.email}")

            return user

        except Exception as e:
            logger.error(f"AuthServiceAPIBackend: Error creating/updating local user: {str(e)}")
            return None


class CachedAuthServiceAPIBackend(AuthServiceAPIBackend):
    """
    Enhanced API-based authentication with caching to reduce API calls and prevent brute force.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate with caching to reduce API load and prevent brute force attacks.
        """
        if username is None or password is None:
            return None

        # Check cache for failed attempts (prevent brute force)
        cache_key = f"auth_fail_{username}"
        if cache.get(cache_key):
            logger.info(f"CachedAuthServiceAPIBackend: Cached failed attempt for: {username}")
            return None

        user = super().authenticate(request, username, password, **kwargs)

        if user is None:
            # Cache failed attempt for 5 minutes
            cache.set(cache_key, True, timeout=300)
            logger.info(f"CachedAuthServiceAPIBackend: Cached failed attempt for: {username}")

        return user