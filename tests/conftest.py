import os
import uuid
from unittest.mock import Mock, patch

import django
import pytest
from django.conf import settings

# Configure Django settings before importing anything else
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")
    django.setup()

from rest_framework.test import APIClient

from apps.management.authentication import RemoteUserProxy
from apps.management.models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
    Team,
    TeamMember,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(scope="session")
def base_user_data():
    """Base user data that stays consistent across tests."""
    return {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "company_id": "550e8400-e29b-41d4-a716-446655440001",
        "email": "testuser@testcompany.com",
        "role": "developer",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture(scope="session")
def base_admin_data():
    """Base admin data that stays consistent across tests."""
    return {
        "user_id": "550e8400-e29b-41d4-a716-446655440002",
        "company_id": "550e8400-e29b-41d4-a716-446655440003",
        "email": "admin@testcompany.com",
        "role": "admin",
        "first_name": "Admin",
        "last_name": "User",
    }


@pytest.fixture
def mock_auth_service(base_user_data):
    """Mock the auth service responses for testing."""
    with (
        patch("apps.management.authentication.requests.post") as mock_post,
        patch("apps.management.authentication.requests.get") as mock_get,
    ):
        # Mock token validation response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            **base_user_data,
        }

        # Mock user data response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = base_user_data

        yield mock_post, mock_get


@pytest.fixture
def mock_user_data(base_user_data):
    """Sample user data for testing."""
    return base_user_data.copy()


@pytest.fixture
def mock_admin_user_data(base_admin_data):
    """Sample admin user data for testing."""
    return base_admin_data.copy()


@pytest.fixture
def mock_user(mock_user_data):
    """Create a mock user proxy object."""
    return RemoteUserProxy(mock_user_data)


@pytest.fixture
def mock_admin_user(mock_admin_user_data):
    """Create a mock admin user proxy object."""
    return RemoteUserProxy(mock_admin_user_data)


@pytest.fixture
def authenticated_client(api_client, mock_auth_service):
    """API client with authentication headers."""
    api_client.credentials(HTTP_AUTHORIZATION="Bearer test-jwt-token")
    return api_client


@pytest.fixture
def admin_authenticated_client(api_client, mock_auth_service, base_admin_data):
    """Admin API client with authentication headers."""
    # Override the mock to return admin user data
    mock_post, mock_get = mock_auth_service
    mock_post.return_value.json.return_value = {
        "valid": True,
        **base_admin_data,
    }

    api_client.credentials(HTTP_AUTHORIZATION="Bearer admin-jwt-token")
    return api_client


@pytest.fixture
def company_id(base_user_data):
    """Sample company ID for testing."""
    return uuid.UUID(base_user_data["company_id"])


@pytest.fixture
@pytest.mark.django_db
def team(company_id, mock_user_data):
    """Create a test team."""
    return Team.objects.create(
        name="Test Team",
        description="A test team for testing purposes",
        company_id=company_id,
        created_by=mock_user_data["user_id"],
    )


@pytest.fixture
@pytest.mark.django_db
def team_with_lead(team, mock_user_data):
    """Create a team with a team lead member."""
    # Use get_or_create to avoid UNIQUE constraint issues
    member, created = TeamMember.objects.get_or_create(team=team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})
    return team, member


@pytest.fixture
@pytest.mark.django_db
def project(team):
    """Create a test project."""
    return Project.objects.create(
        name="Test Project",
        description="A test project for testing purposes",
        team=team,
        repository_url="https://github.com/testuser/test-repo",
        url="https://testproject.com",
    )


@pytest.fixture
@pytest.mark.django_db
def team_member(team):
    """Create a test team member."""
    # Use a different user_id to avoid conflicts
    user_id = "550e8400-e29b-41d4-a716-446655440004"
    member, created = TeamMember.objects.get_or_create(team=team, user_id=user_id, defaults={"role": "developer"})
    return member


@pytest.fixture
@pytest.mark.django_db
def team_lead(team, mock_user_data):
    """Create a test team lead."""
    member, created = TeamMember.objects.get_or_create(team=team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})
    return member


@pytest.fixture
@pytest.mark.django_db
def integration(project):
    """Create a test integration."""
    return Integration.objects.create(
        project=project,
        type="github",
        config_data={"repository_owner": "testuser", "repository_name": "test-repo"},
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def github_integration(project):
    """Create a test GitHub integration."""
    return GitHubIntegration.objects.create(
        project=project,
        repository_owner="testuser",
        repository_name="test-repo",
        access_token="test-access-token",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def code_commit(project):
    """Create a test code commit."""
    return CodeCommit.objects.create(
        project=project,
        commit_hash="abc123def456",
        author_email="developer@testcompany.com",
        author_name="Test Developer",
        message="Test commit message",
        branch="main",
        timestamp="2023-01-01T12:00:00Z",
        files_changed=3,
        insertions=25,
        deletions=10,
    )


@pytest.fixture
def sample_teams_data():
    """Sample data for creating multiple teams."""
    return [
        {"name": "Frontend Team", "description": "Frontend development team"},
        {"name": "Backend Team", "description": "Backend development team"},
        {"name": "DevOps Team", "description": "DevOps and infrastructure team"},
    ]


@pytest.fixture
def sample_projects_data():
    """Sample data for creating multiple projects."""
    return [
        {
            "name": "Frontend App",
            "description": "Main frontend application",
            "repository_url": "https://github.com/company/frontend-app",
            "url": "https://app.company.com",
        },
        {
            "name": "API Service",
            "description": "Main backend API service",
            "repository_url": "https://github.com/company/api-service",
        },
        {
            "name": "Mobile App",
            "description": "Mobile application",
            "repository_url": "https://github.com/company/mobile-app",
        },
    ]
