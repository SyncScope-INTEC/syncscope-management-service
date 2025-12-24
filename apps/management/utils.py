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


def send_project_invitation_email(
    invitee_email, inviter_name, inviter_email, project_name, team_name, role, invitation_token
):
    """
    Send project invitation email via alerts-service.

    Args:
        invitee_email: Email of person being invited
        inviter_name: Name of person sending invitation
        inviter_email: Email of person sending invitation
        project_name: Name of the project
        team_name: Name of the team
        role: Project role (supervisor/developer)
        invitation_token: Unique invitation token

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    import logging

    import requests

    logger = logging.getLogger(__name__)

    alerts_service_url = settings.ALERTS_SERVICE_URL
    frontend_url = settings.FRONTEND_URL

    # Prepare the payload
    payload = {
        "invitee_email": invitee_email,
        "inviter_name": inviter_name,
        "inviter_email": inviter_email,
        "project_name": project_name,
        "team_name": team_name,
        "role": role,
        "invitation_token": invitation_token,
        "frontend_url": frontend_url,
        "expiration_days": 7,
    }

    try:
        # Call alerts-service API
        response = requests.post(
            f"{alerts_service_url}/alerts/send-project-invitation-email/",
            json=payload,
            timeout=10,
        )
        return response.status_code == 200
    except Exception as e:
        # Log error but don't expose to user
        logger.error(f"Error sending project invitation email: {str(e)}")
        return False
