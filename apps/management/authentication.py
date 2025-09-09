"""
Remote JWT authentication backend that integrates with the auth service.
"""

import logging
import requests

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

logger = logging.getLogger("apps.management")


class RemoteUserProxy:
    """
    Proxy object representing a user from the auth service.
    """

    def __init__(self, user_data):
        self.id = user_data.get("user_id")
        self.email = user_data.get("email", "")
        self.role = user_data.get("role", "developer")
        self.company_id = user_data.get("company_id")
        self.first_name = user_data.get("first_name", "")
        self.last_name = user_data.get("last_name", "")
        self.is_active = True
        self.is_authenticated = True
        self.is_anonymous = False

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def has_perm(self, perm, obj=None):
        """Simple permission check based on role."""
        if self.role == "admin":
            return True
        # Add more granular permissions as needed
        return False

    def has_module_perms(self, app_label):
        """Module permissions check."""
        return self.role == "admin"


class RemoteJWTAuthentication(BaseAuthentication):
    """
    Authentication backend that validates JWT tokens with the remote auth service.
    """

    def authenticate(self, request):
        """
        Authenticate the request by validating the JWT token with the auth service.
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1]

        try:
            user_data = self._validate_token_with_auth_service(token)
            if user_data:
                user = RemoteUserProxy(user_data)
                return (user, token)
        except Exception as e:
            logger.warning(f"JWT authentication failed: {str(e)}")
            raise exceptions.AuthenticationFailed("Invalid token")

        return None

    def _validate_token_with_auth_service(self, token):
        """
        Validate the JWT token with the remote auth service.
        """
        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        verify_url = f"{auth_service_url}/auth/verify-token/"

        try:
            response = requests.post(
                verify_url,
                json={"token": token},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    return data
                else:
                    logger.warning(f"Token validation failed: {data.get('error', 'Unknown error')}")
                    return None
            else:
                logger.error(f"Auth service returned status {response.status_code}")
                return None

        except requests.RequestException as e:
            logger.error(f"Failed to contact auth service: {str(e)}")
            raise exceptions.AuthenticationFailed("Authentication service unavailable")

    def authenticate_header(self, request):
        """
        Return the authentication header for 401 responses.
        """
        return "Bearer"


class AuthServiceIntegration:
    """
    Helper class for interacting with the auth service.
    """

    @staticmethod
    def get_user_by_id(user_id, token=None):
        """
        Fetch user details from the auth service.
        """
        auth_service_url = getattr(settings, "AUTH_SERVICE_URL", "http://localhost:8000")
        user_url = f"{auth_service_url}/auth/profile/"

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(user_url, headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user {user_id}: {str(e)}")
            return None

    @staticmethod
    def get_company_by_id(company_id, token=None):
        """
        Fetch company details from the auth service.
        """
        # This would be implemented when the auth service has a company endpoint
        # For now, return basic structure
        return {
            "id": company_id,
            "name": "Unknown Company",
        }

    @staticmethod
    def check_user_permissions(user_id, required_permissions, token=None):
        """
        Check if a user has specific permissions.
        """
        # This would integrate with the auth service's permission system
        # For now, implement basic role-based checks
        user_data = AuthServiceIntegration.get_user_by_id(user_id, token)
        if not user_data:
            return False

        role = user_data.get("role", "developer")
        if role == "admin":
            return True

        # Add more granular permission checks as needed
        return False