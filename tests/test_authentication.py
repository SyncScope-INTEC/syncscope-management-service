import uuid
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.management.authentication import (
    AuthServiceIntegration,
    RemoteJWTAuthentication,
    RemoteUserProxy,
)


class TestRemoteUserProxy:

    def test_user_proxy_initialization(self):
        """Test RemoteUserProxy initialization with user data."""
        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "role": "developer",
            "company_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
        }

        user = RemoteUserProxy(user_data)

        assert user.id == user_data["user_id"]
        assert user.email == user_data["email"]
        assert user.role == user_data["role"]
        assert user.company_id == user_data["company_id"]
        assert user.first_name == user_data["first_name"]
        assert user.last_name == user_data["last_name"]
        assert user.is_active is True
        assert user.is_authenticated is True
        assert user.is_anonymous is False

    def test_user_proxy_defaults(self):
        """Test RemoteUserProxy with minimal data and defaults."""
        user_data = {"user_id": str(uuid.uuid4())}
        user = RemoteUserProxy(user_data)

        assert user.id == user_data["user_id"]
        assert user.email == ""
        assert user.role == "developer"
        assert user.company_id is None
        assert user.first_name == ""
        assert user.last_name == ""

    def test_user_proxy_full_name_property(self):
        """Test full_name property."""
        user_data = {
            "user_id": str(uuid.uuid4()),
            "first_name": "John",
            "last_name": "Doe",
        }
        user = RemoteUserProxy(user_data)

        assert user.full_name == "John Doe"

    def test_user_proxy_full_name_property_empty(self):
        """Test full_name property with empty names."""
        user_data = {"user_id": str(uuid.uuid4())}
        user = RemoteUserProxy(user_data)

        assert user.full_name == ""

    def test_user_proxy_str_representation(self):
        """Test string representation."""
        user_data = {
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        user = RemoteUserProxy(user_data)

        assert str(user) == "John Doe (test@example.com)"

    def test_user_proxy_permissions_admin(self):
        """Test permission checking for admin users."""
        user_data = {"user_id": str(uuid.uuid4()), "role": "admin"}
        user = RemoteUserProxy(user_data)

        assert user.has_perm("any_permission") is True
        assert user.has_module_perms("any_app") is True

    def test_user_proxy_permissions_non_admin(self):
        """Test permission checking for non-admin users."""
        user_data = {"user_id": str(uuid.uuid4()), "role": "developer"}
        user = RemoteUserProxy(user_data)

        assert user.has_perm("any_permission") is False
        assert user.has_module_perms("any_app") is False


class TestRemoteJWTAuthentication:

    def test_authenticate_no_header(self):
        """Test authentication with no authorization header."""
        factory = APIRequestFactory()
        request = factory.get("/api/test/")

        auth = RemoteJWTAuthentication()
        result = auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_header_format(self):
        """Test authentication with invalid header format."""
        factory = APIRequestFactory()
        request = factory.get("/api/test/", HTTP_AUTHORIZATION="InvalidFormat token")

        auth = RemoteJWTAuthentication()
        result = auth.authenticate(request)

        assert result is None

    @patch("apps.management.authentication.requests.post")
    def test_authenticate_success(self, mock_post):
        """Test successful authentication."""
        # Mock auth service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "valid": True,
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "role": "developer",
            "company_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
        }
        mock_post.return_value = mock_response

        factory = APIRequestFactory()
        request = factory.get("/api/test/", HTTP_AUTHORIZATION="Bearer valid-token")

        auth = RemoteJWTAuthentication()
        user, token = auth.authenticate(request)

        assert isinstance(user, RemoteUserProxy)
        assert token == "valid-token"
        assert user.email == "test@example.com"
        assert user.role == "developer"

    @patch("apps.management.authentication.requests.post")
    def test_authenticate_invalid_token(self, mock_post):
        """Test authentication with invalid token."""
        # Mock auth service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"valid": False, "error": "Invalid token"}
        mock_post.return_value = mock_response

        factory = APIRequestFactory()
        request = factory.get("/api/test/", HTTP_AUTHORIZATION="Bearer invalid-token")

        auth = RemoteJWTAuthentication()
        result = auth.authenticate(request)

        assert result is None

    @patch("apps.management.authentication.requests.post")
    def test_authenticate_service_error(self, mock_post):
        """Test authentication when auth service returns error."""
        # Mock auth service error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        factory = APIRequestFactory()
        request = factory.get("/api/test/", HTTP_AUTHORIZATION="Bearer token")

        auth = RemoteJWTAuthentication()
        result = auth.authenticate(request)

        assert result is None

    @patch("apps.management.authentication.requests.post")
    def test_authenticate_service_unavailable(self, mock_post):
        """Test authentication when auth service is unavailable."""
        # Mock connection error
        mock_post.side_effect = Exception("Connection refused")

        factory = APIRequestFactory()
        request = factory.get("/api/test/", HTTP_AUTHORIZATION="Bearer token")

        auth = RemoteJWTAuthentication()

        with pytest.raises(AuthenticationFailed, match="Authentication service unavailable"):
            auth.authenticate(request)

    def test_authenticate_header(self):
        """Test authentication header for 401 responses."""
        factory = APIRequestFactory()
        request = factory.get("/api/test/")

        auth = RemoteJWTAuthentication()
        header = auth.authenticate_header(request)

        assert header == "Bearer"

    @patch("apps.management.authentication.requests.post")
    def test_validate_token_with_auth_service(self, mock_post):
        """Test token validation method."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "valid": True,
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
        }
        mock_post.return_value = mock_response

        auth = RemoteJWTAuthentication()
        result = auth._validate_token_with_auth_service("test-token")

        assert result is not None
        assert result["valid"] is True
        assert result["email"] == "test@example.com"

        # Verify correct API call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "verify-token" in args[0]
        assert kwargs["json"]["token"] == "test-token"


class TestAuthServiceIntegration:

    @patch("apps.management.authentication.requests.get")
    def test_get_user_by_id_success(self, mock_get):
        """Test successful user retrieval."""
        user_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": user_id,
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
        }
        mock_get.return_value = mock_response

        result = AuthServiceIntegration.get_user_by_id(user_id, "test-token")

        assert result is not None
        assert result["user_id"] == user_id
        assert result["email"] == "test@example.com"

        # Verify correct API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert f"users/{user_id}" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"

    @patch("apps.management.authentication.requests.get")
    def test_get_user_by_id_not_found(self, mock_get):
        """Test user retrieval when user not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = AuthServiceIntegration.get_user_by_id(str(uuid.uuid4()), "test-token")

        assert result is None

    @patch("apps.management.authentication.requests.get")
    def test_get_user_by_id_service_error(self, mock_get):
        """Test user retrieval when service has error."""
        mock_get.side_effect = Exception("Service unavailable")

        result = AuthServiceIntegration.get_user_by_id(str(uuid.uuid4()), "test-token")

        assert result is None

    @patch("apps.management.authentication.requests.get")
    def test_get_user_by_id_no_token(self, mock_get):
        """Test user retrieval without token."""
        user_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_id": user_id}
        mock_get.return_value = mock_response

        result = AuthServiceIntegration.get_user_by_id(user_id)

        assert result is not None

        # Verify no Authorization header was sent
        args, kwargs = mock_get.call_args
        assert "Authorization" not in kwargs["headers"]

    def test_get_company_by_id(self):
        """Test company retrieval (stub implementation)."""
        company_id = str(uuid.uuid4())
        result = AuthServiceIntegration.get_company_by_id(company_id)

        assert result is not None
        assert result["id"] == company_id
        assert result["name"] == "Unknown Company"

    @patch("apps.management.authentication.AuthServiceIntegration.get_user_by_id")
    def test_check_user_permissions_admin(self, mock_get_user):
        """Test permission checking for admin user."""
        mock_get_user.return_value = {"user_id": str(uuid.uuid4()), "role": "admin"}

        result = AuthServiceIntegration.check_user_permissions(str(uuid.uuid4()), ["manage_teams"], "test-token")

        assert result is True

    @patch("apps.management.authentication.AuthServiceIntegration.get_user_by_id")
    def test_check_user_permissions_non_admin(self, mock_get_user):
        """Test permission checking for non-admin user."""
        mock_get_user.return_value = {"user_id": str(uuid.uuid4()), "role": "developer"}

        result = AuthServiceIntegration.check_user_permissions(str(uuid.uuid4()), ["manage_teams"], "test-token")

        assert result is False

    @patch("apps.management.authentication.AuthServiceIntegration.get_user_by_id")
    def test_check_user_permissions_no_user(self, mock_get_user):
        """Test permission checking when user not found."""
        mock_get_user.return_value = None

        result = AuthServiceIntegration.check_user_permissions(str(uuid.uuid4()), ["manage_teams"], "test-token")

        assert result is False


@pytest.mark.django_db
class TestAuthenticationIntegration:

    @patch("apps.management.authentication.requests.post")
    def test_full_authentication_flow(self, mock_post):
        """Test complete authentication flow with API client."""
        from django.urls import reverse
        from rest_framework.test import APIClient

        # Mock auth service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "valid": True,
            "user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "role": "admin",
            "company_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
        }
        mock_post.return_value = mock_response

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer test-token")

        response = client.get("/management/teams/")

        # Should pass authentication
        assert response.status_code in [200, 404]  # 404 if no teams found

        # Verify auth service was called
        mock_post.assert_called_once()

    def test_authentication_required_endpoints(self):
        """Test that protected endpoints require authentication."""
        from rest_framework.test import APIClient

        client = APIClient()

        # Test various endpoints without authentication
        endpoints = [
            "/management/teams/",
            "/management/projects/",
            "/management/team-members/",
            "/management/integrations/",
            "/management/github-integrations/",
            "/management/commits/",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"
