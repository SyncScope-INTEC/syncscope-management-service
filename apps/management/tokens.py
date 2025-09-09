"""
Custom JWT token classes with enhanced security for CVE-2024-22513 mitigation.
"""

import hashlib

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


class SecureRefreshToken(RefreshToken):
    """
    Enhanced refresh token that includes user validation checks
    to mitigate CVE-2024-22513 vulnerability.
    """

    @classmethod
    def for_user(cls, user):
        """
        Enhanced for_user method with proper user validation.

        This method adds additional security checks to ensure:
        1. User exists and is active
        2. User account is not disabled
        3. Password hash is included for token invalidation on password change
        """
        # Validate user exists and is active
        if not user or not user.is_active:
            raise ValueError("Cannot create token for inactive or non-existent user")

        # Get the token
        token = super().for_user(user)

        # Add password hash for token invalidation on password change
        if hasattr(user, "password") and user.password:
            password_hash = hashlib.md5(user.password.encode()).hexdigest().upper()
            token["password_hash"] = password_hash

        return token

    def check_user_active(self):
        """
        Check if the user associated with this token is still active.
        """
        try:
            user_id = self.payload.get("user_id")
            if not user_id:
                return False

            user = User.objects.get(id=user_id)
            return user.is_active
        except User.DoesNotExist:
            return False

    def check_password_unchanged(self):
        """
        Check if the user's password has been changed since token creation.
        """
        try:
            user_id = self.payload.get("user_id")
            stored_hash = self.payload.get("password_hash")

            if not user_id or not stored_hash:
                return True  # Skip check if data not available

            user = User.objects.get(id=user_id)
            current_hash = hashlib.md5(user.password.encode()).hexdigest().upper()

            return stored_hash.upper() == current_hash
        except User.DoesNotExist:
            return False


class SecureAccessToken(AccessToken):
    """
    Enhanced access token with user validation checks.
    """

    @classmethod
    def for_user(cls, user):
        """
        Enhanced for_user method with proper user validation.
        """
        # Validate user exists and is active
        if not user or not user.is_active:
            raise ValueError("Cannot create token for inactive or non-existent user")

        # Get the token
        token = super().for_user(user)

        # Add password hash for token invalidation on password change
        if hasattr(user, "password") and user.password:
            password_hash = hashlib.md5(user.password.encode()).hexdigest().upper()
            token["password_hash"] = password_hash

        return token
