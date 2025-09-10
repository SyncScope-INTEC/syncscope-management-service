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


@pytest.fixture
def mock_auth_service():
    """Mock the auth service responses for testing."""
    with patch("apps.management.authentication.requests.post") as mock_post, patch(
        "apps.management.authentication.requests.get"
    ) as mock_get:
        # Mock token validation response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": str(uuid.uuid4()),
            "email": "testuser@testcompany.com",
            "role": "developer",
            "company_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
        }

        # Mock user data response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "user_id": str(uuid.uuid4()),
            "email": "testuser@testcompany.com",
            "role": "developer",
            "company_id": str(uuid.uuid4()),
            "first_name": "Test",
            "last_name": "User",
        }

        yield mock_post, mock_get


@pytest.fixture
def mock_user_data():
    """Sample user data for testing."""
    return {
        "user_id": str(uuid.uuid4()),
        "email": "testuser@testcompany.com",
        "role": "developer",
        "company_id": str(uuid.uuid4()),
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def mock_admin_user_data():
    """Sample admin user data for testing."""
    return {
        "user_id": str(uuid.uuid4()),
        "email": "admin@testcompany.com",
        "role": "admin",
        "company_id": str(uuid.uuid4()),
        "first_name": "Admin",
        "last_name": "User",
    }


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
def admin_authenticated_client(api_client, mock_auth_service):
    """Admin API client with authentication headers."""
    # Override the mock to return admin user data
    mock_post, mock_get = mock_auth_service
    mock_post.return_value.json.return_value = {
        "valid": True,
        "user_id": str(uuid.uuid4()),
        "email": "admin@testcompany.com",
        "role": "admin",
        "company_id": str(uuid.uuid4()),
        "first_name": "Admin",
        "last_name": "User",
    }

    api_client.credentials(HTTP_AUTHORIZATION="Bearer admin-jwt-token")
    return api_client


@pytest.fixture
def company_id():
    """Sample company ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def team(company_id, mock_user_data):
    """Create a test team."""
    return Team.objects.create(
        name="Test Team",
        description="A test team for testing purposes",
        company_id=company_id,
        created_by=mock_user_data["user_id"],
    )


@pytest.fixture
def team_with_lead(team, mock_user_data):
    """Create a team with a team lead member."""
    member = TeamMember.objects.create(
        team=team, user_id=mock_user_data["user_id"], role="lead"
    )
    return team, member


@pytest.fixture
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
def team_member(team, mock_user_data):
    """Create a test team member."""
    return TeamMember.objects.create(
        team=team, user_id=mock_user_data["user_id"], role="developer"
    )


@pytest.fixture
def team_lead(team, mock_user_data):
    """Create a test team lead."""
    return TeamMember.objects.create(
        team=team, user_id=mock_user_data["user_id"], role="lead"
    )


@pytest.fixture
def integration(project):
    """Create a test integration."""
    return Integration.objects.create(
        project=project,
        type="github",
        config_data={"repository_owner": "testuser", "repository_name": "test-repo"},
        is_active=True,
    )


@pytest.fixture
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
