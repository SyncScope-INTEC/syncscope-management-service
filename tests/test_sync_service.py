"""Tests for the sync_service module."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.management.models import CodeCommit, GitHubIntegration, Project, Team
from apps.management.sync_service import (
    SyncResult,
    sync_all_project_integrations,
    sync_from_github_api,
    sync_from_monitoring_service,
    sync_integration,
)


@pytest.fixture
def team(db):
    """Create a test team."""
    return Team.objects.create(
        name="Test Team",
        company_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
    )


@pytest.fixture
def project(team):
    """Create a test project."""
    return Project.objects.create(
        name="Test Project",
        team=team,
        repository_url="https://github.com/testowner/testrepo",
    )


@pytest.fixture
def github_integration(project):
    """Create a test GitHub integration."""
    return GitHubIntegration.objects.create(
        project=project,
        repository_owner="testowner",
        repository_name="testrepo",
        access_token="test-token-12345",
        is_active=True,
    )


@pytest.mark.django_db
class TestSyncResult:
    """Tests for SyncResult class."""

    def test_sync_result_initialization(self):
        """Test SyncResult initializes with correct defaults."""
        result = SyncResult()
        assert result.commits_created == 0
        assert result.commits_skipped == 0
        assert result.errors == []

    def test_sync_result_str(self):
        """Test SyncResult string representation."""
        result = SyncResult()
        result.commits_created = 5
        result.commits_skipped = 3
        result.errors = ["error1", "error2"]
        assert str(result) == "Created: 5, Skipped: 3, Errors: 2"


@pytest.mark.django_db
class TestSyncFromMonitoringService:
    """Tests for sync_from_monitoring_service function."""

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_success(self, mock_get, github_integration):
        """Test successful sync from monitoring service."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "git_events": [
                {
                    "commit_hash": "abc123def456789012345678901234567890abcd",
                    "author_email": "test@example.com",
                    "author_name": "Test Author",
                    "commit_message": "Test commit message",
                    "branch_name": "main",
                    "timestamp": "2026-01-15T10:00:00Z",
                    "files_changed": 5,
                    "insertions": 100,
                    "deletions": 50,
                }
            ],
            "count": 1,
        }
        mock_get.return_value = mock_response

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 1
        assert result.commits_skipped == 0
        assert len(result.errors) == 0

        # Verify commit was created
        commit = CodeCommit.objects.get(
            project=github_integration.project,
            commit_hash="abc123def456789012345678901234567890abcd",
        )
        assert commit.author_email == "test@example.com"
        assert commit.author_name == "Test Author"

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_empty_response(self, mock_get, github_integration):
        """Test sync with no git events."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"git_events": [], "count": 0}
        mock_get.return_value = mock_response

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 0
        assert result.commits_skipped == 0
        assert len(result.errors) == 0

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_duplicate_commit(self, mock_get, github_integration):
        """Test sync skips existing commits."""
        # Create existing commit
        CodeCommit.objects.create(
            project=github_integration.project,
            commit_hash="abc123def456789012345678901234567890abcd",
            author_email="test@example.com",
            author_name="Test Author",
            message="Existing commit",
            timestamp=timezone.now(),
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "git_events": [
                {
                    "commit_hash": "abc123def456789012345678901234567890abcd",
                    "author_email": "test@example.com",
                    "author_name": "Test Author",
                    "commit_message": "Test commit message",
                    "branch_name": "main",
                    "timestamp": "2026-01-15T10:00:00Z",
                }
            ],
            "count": 1,
        }
        mock_get.return_value = mock_response

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 0
        assert result.commits_skipped == 1

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_api_error(self, mock_get, github_integration):
        """Test sync handles API errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 0
        assert len(result.errors) == 1
        assert "500" in result.errors[0]

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_connection_error(self, mock_get, github_integration):
        """Test sync handles connection errors."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 0
        assert len(result.errors) == 1
        assert "Connection failed" in result.errors[0]

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_missing_commit_hash(self, mock_get, github_integration):
        """Test sync skips events without commit hash."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "git_events": [
                {
                    "commit_hash": None,
                    "author_email": "test@example.com",
                    "author_name": "Test Author",
                }
            ],
            "count": 1,
        }
        mock_get.return_value = mock_response

        result = sync_from_monitoring_service(github_integration)

        assert result.commits_created == 0
        assert result.commits_skipped == 1

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_monitoring_uses_last_sync(self, mock_get, github_integration):
        """Test sync uses last_sync timestamp."""
        github_integration.last_sync = timezone.now() - timedelta(hours=1)
        github_integration.save()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"git_events": [], "count": 0}
        mock_get.return_value = mock_response

        sync_from_monitoring_service(github_integration)

        # Verify the since parameter was passed
        call_args = mock_get.call_args
        assert "since" in call_args[1]["params"]


@pytest.mark.django_db
class TestSyncFromGitHubApi:
    """Tests for sync_from_github_api function."""

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_github_success(self, mock_get, github_integration):
        """Test successful sync from GitHub API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "sha": "abc123def456789012345678901234567890abcd",
                "commit": {
                    "author": {
                        "name": "Test Author",
                        "email": "test@example.com",
                        "date": "2026-01-15T10:00:00Z",
                    },
                    "message": "Test commit from GitHub",
                },
                "stats": {"additions": 100, "deletions": 50},
            }
        ]
        mock_get.return_value = mock_response

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 1
        assert result.commits_skipped == 0
        assert len(result.errors) == 0

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_github_empty_commits(self, mock_get, github_integration):
        """Test sync with no commits from GitHub."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 0
        assert result.commits_skipped == 0

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_github_auth_failure(self, mock_get, github_integration):
        """Test sync handles GitHub auth failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 0
        assert len(result.errors) == 1
        assert "authentication failed" in result.errors[0].lower()

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_github_not_found(self, mock_get, github_integration):
        """Test sync handles GitHub 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 0
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()

    def test_sync_from_github_no_token(self, github_integration):
        """Test sync returns error without access token."""
        github_integration.access_token = ""
        github_integration.save()

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 0
        assert len(result.errors) == 1
        assert "No access token" in result.errors[0]

    @patch("apps.management.sync_service.requests.get")
    def test_sync_from_github_duplicate_commit(self, mock_get, github_integration):
        """Test sync skips existing commits from GitHub."""
        # Create existing commit
        CodeCommit.objects.create(
            project=github_integration.project,
            commit_hash="abc123def456789012345678901234567890abcd",
            author_email="test@example.com",
            author_name="Test Author",
            message="Existing commit",
            timestamp=timezone.now(),
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "sha": "abc123def456789012345678901234567890abcd",
                "commit": {
                    "author": {
                        "name": "Test Author",
                        "email": "test@example.com",
                        "date": "2026-01-15T10:00:00Z",
                    },
                    "message": "Test commit",
                },
            }
        ]
        mock_get.return_value = mock_response

        result = sync_from_github_api(github_integration)

        assert result.commits_created == 0
        assert result.commits_skipped == 1


@pytest.mark.django_db
class TestSyncIntegration:
    """Tests for sync_integration function."""

    @patch("apps.management.sync_service.requests.get")
    def test_sync_integration_both_sources(self, mock_get, github_integration):
        """Test sync from both monitoring and GitHub."""
        # First call for monitoring, second for GitHub
        mock_monitoring_response = Mock()
        mock_monitoring_response.status_code = 200
        mock_monitoring_response.json.return_value = {"git_events": [], "count": 0}

        mock_github_response = Mock()
        mock_github_response.status_code = 200
        mock_github_response.json.return_value = []

        def side_effect(url, **kwargs):
            if "github.com" in url:
                return mock_github_response
            return mock_monitoring_response

        mock_get.side_effect = side_effect

        results = sync_integration(github_integration)

        assert "monitoring" in results
        assert "github" in results
        assert results["total_created"] == 0

    @patch("apps.management.sync_service.requests.get")
    def test_sync_integration_monitoring_only(self, mock_get, github_integration):
        """Test sync from monitoring service only."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"git_events": [], "count": 0}
        mock_get.return_value = mock_response

        results = sync_integration(github_integration, sync_monitoring=True, sync_github=False)

        assert results["monitoring"] is not None
        assert results["github"] is None

    @patch("apps.management.sync_service.requests.get")
    def test_sync_integration_github_only(self, mock_get, github_integration):
        """Test sync from GitHub only."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        results = sync_integration(github_integration, sync_monitoring=False, sync_github=True)

        assert results["monitoring"] is None
        assert results["github"] is not None

    @patch("apps.management.sync_service.requests.get")
    def test_sync_integration_updates_last_sync(self, mock_get, github_integration):
        """Test sync updates last_sync timestamp."""
        original_last_sync = github_integration.last_sync

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"git_events": [], "count": 0}
        mock_get.return_value = mock_response

        sync_integration(github_integration, sync_github=False)

        github_integration.refresh_from_db()
        assert github_integration.last_sync is not None
        assert github_integration.last_sync != original_last_sync


@pytest.mark.django_db
class TestSyncAllProjectIntegrations:
    """Tests for sync_all_project_integrations function."""

    @patch("apps.management.sync_service.requests.get")
    def test_sync_all_integrations(self, mock_get, project, github_integration):
        """Test sync all integrations for a project."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"git_events": [], "count": 0}
        mock_get.return_value = mock_response

        results = sync_all_project_integrations(project, sync_github=False)

        assert len(results) == 1
        assert results[0]["repository"] == "testowner/testrepo"

    @patch("apps.management.sync_service.requests.get")
    def test_sync_all_integrations_inactive_skipped(self, mock_get, project, github_integration):
        """Test inactive integrations are skipped."""
        github_integration.is_active = False
        github_integration.save()

        results = sync_all_project_integrations(project)

        assert len(results) == 0
