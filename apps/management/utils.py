import hashlib
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from config.database_retry import database_retry

from .models import UserSession


def generate_session_token():
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)


def hash_token(token):
    """Hash a token for secure storage"""
    return hashlib.sha256(token.encode()).hexdigest()


@database_retry()
def create_user_session(user, request=None):
    """Create a new user session"""
    token = generate_session_token()
    token_hash = hash_token(token)

    user_agent = ""
    ip_address = None

    if request:
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("REMOTE_ADDR")

    session = UserSession.objects.create(
        user=user,
        token_hash=token_hash,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=timezone.now() + timedelta(days=7),
    )

    return session, token


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@database_retry()
def invalidate_user_sessions(user, exclude_session_id=None):
    """Invalidate all user sessions except optionally one"""
    sessions = user.sessions.all()
    if exclude_session_id:
        sessions = sessions.exclude(id=exclude_session_id)
    sessions.delete()


def cleanup_expired_sessions():
    """Clean up expired sessions"""
    UserSession.cleanup_expired_sessions()


def get_client_ip(request):
    """Get client IP address from request"""
    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        return x_real_ip

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "127.0.0.1")


@database_retry()
def validate_session_token(token):
    """Validate a session token and return the session if valid"""
    if not token:
        return None

    token_hash = hash_token(token)
    return UserSession.get_active_session(token_hash)


def extract_domain_from_email(email):
    """Extract domain from email address"""
    if "@" not in email:
        return None
    return f"@{email.split('@')[1]}"
