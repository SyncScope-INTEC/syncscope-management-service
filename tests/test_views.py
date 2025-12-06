import json
import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.management.models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    OrganizationSettings,
    Project,
    Team,
    TeamMember,
)


@pytest.mark.django_db
class TestTeamViewSet:

    def test_list_teams_authenticated(self, authenticated_client, team, mock_auth_service):
        """Test listing teams as authenticated user."""
        url = reverse("management:team-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0  # May be empty if no teams for user's company

    def test_list_teams_unauthenticated(self, api_client):
        """Test that unauthenticated users cannot list teams."""
        url = reverse("management:team-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_team_success(self, authenticated_client, mock_auth_service):
        """Test successful team creation."""
        url = reverse("management:team-list")
        data = {"name": "New Test Team", "description": "A new team for testing"}

        response = authenticated_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert Team.objects.filter(name="New Test Team").exists()

    def test_create_team_duplicate_name(self, authenticated_client, team, mock_auth_service):
        """Test creating team with duplicate name in same company."""
        url = reverse("management:team-list")
        data = {"name": team.name, "description": "Duplicate name"}

        response = authenticated_client.post(url, data)
        # Should succeed as names can be duplicate across companies
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_team_success(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test retrieving team details."""
        team, lead = team_with_lead
        url = reverse("management:team-detail", args=[team.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == team.name
        assert "members_count" in response.data
        assert "projects_count" in response.data

    def test_update_team_as_lead(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test updating team as team lead."""
        team, lead = team_with_lead
        url = reverse("management:team-detail", args=[team.id])
        data = {"name": "Updated Team Name", "description": "Updated description"}

        response = authenticated_client.put(url, data)

        assert response.status_code == status.HTTP_200_OK
        team.refresh_from_db()
        assert team.name == "Updated Team Name"

    def test_delete_team_as_lead(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test deleting team as team lead."""
        team, lead = team_with_lead
        url = reverse("management:team-detail", args=[team.id])

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Team.objects.filter(id=team.id).exists()

    def test_team_members_endpoint(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test getting team members."""
        team, lead = team_with_lead
        url = reverse("management:team-members", args=[team.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1  # At least the lead

    def test_add_team_member(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test adding a member to team."""
        team, lead = team_with_lead
        url = reverse("management:team-members", args=[team.id])
        data = {"user_id": str(uuid.uuid4()), "role": "developer"}

        response = authenticated_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert TeamMember.objects.filter(team=team, user_id=data["user_id"]).exists()

    def test_team_projects_endpoint(self, authenticated_client, team_with_lead, project, mock_auth_service):
        """Test getting team projects."""
        team, lead = team_with_lead
        # Update project to belong to this team
        project.team = team
        project.save()

        url = reverse("management:team-projects", args=[team.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestProjectViewSet:

    def test_list_projects_authenticated(self, authenticated_client, project, mock_auth_service):
        """Test listing projects as authenticated user."""
        url = reverse("management:project-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0

    def test_create_project_success(self, authenticated_client, team_with_lead, mock_auth_service):
        """Test successful project creation."""
        team, lead = team_with_lead
        url = reverse("management:project-list")
        data = {
            "name": "New Test Project",
            "description": "A new project for testing",
            "team_id": str(team.id),
            "repository_url": "https://github.com/test/new-repo",
            "url": "https://newproject.com",
        }

        response = authenticated_client.post(url, data)

        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.filter(name="New Test Project").exists()

    def test_create_project_invalid_team(self, authenticated_client, mock_auth_service):
        """Test creating project with invalid team ID."""
        url = reverse("management:project-list")
        data = {
            "name": "Test Project",
            "team_id": str(uuid.uuid4()),  # Non-existent team
        }

        response = authenticated_client.post(url, data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_project_success(self, authenticated_client, project, team_with_lead, mock_auth_service):
        """Test retrieving project details."""
        team, lead = team_with_lead
        project.team = team
        project.save()

        url = reverse("management:project-detail", args=[project.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == project.name
        assert "integrations_count" in response.data
        assert "commits_count" in response.data
        assert "latest_commit" in response.data

    def test_project_integrations_endpoint(self, authenticated_client, project, team_with_lead, mock_auth_service):
        """Test getting project integrations."""
        team, lead = team_with_lead
        project.team = team
        project.save()

        url = reverse("management:project-integrations", args=[project.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_create_project_integration(self, authenticated_client, project, team_with_lead, mock_auth_service):
        """Test creating project integration."""
        team, lead = team_with_lead
        project.team = team
        project.save()

        url = reverse("management:project-integrations", args=[project.id])
        data = {
            "type": "github",
            "config_data": {
                "repository_owner": "testuser",
                "repository_name": "test-repo",
            },
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Integration.objects.filter(project=project, type="github").exists()

    def test_project_commits_endpoint(
        self,
        authenticated_client,
        project,
        team_with_lead,
        code_commit,
        mock_auth_service,
    ):
        """Test getting project commits."""
        team, lead = team_with_lead
        project.team = team
        project.save()
        code_commit.project = project
        code_commit.save()

        url = reverse("management:project-commits", args=[project.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestTeamMemberViewSet:

    def test_list_team_members(self, authenticated_client, team_member, mock_auth_service):
        """Test listing team members."""
        url = reverse("management:teammember-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0

    def test_retrieve_team_member(self, authenticated_client, team_member, team_with_lead, mock_auth_service):
        """Test retrieving team member details."""
        team, lead = team_with_lead
        team_member.team = team
        team_member.save()

        url = reverse("management:teammember-detail", args=[team_member.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["user_id"] == str(team_member.user_id)
        assert "user_email" in response.data
        assert "user_name" in response.data

    def test_update_team_member_role(self, authenticated_client, team_member, team_with_lead, mock_auth_service):
        """Test updating team member role."""
        team, lead = team_with_lead
        team_member.team = team
        team_member.save()

        url = reverse("management:teammember-detail", args=[team_member.id])
        data = {"role": "senior_developer"}

        response = authenticated_client.patch(url, data)

        assert response.status_code == status.HTTP_200_OK
        team_member.refresh_from_db()
        assert team_member.role == "senior_developer"

    def test_remove_team_member(self, authenticated_client, team_member, team_with_lead, mock_auth_service):
        """Test removing team member."""
        team, lead = team_with_lead
        team_member.team = team
        team_member.save()

        url = reverse("management:teammember-detail", args=[team_member.id])

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not TeamMember.objects.filter(id=team_member.id).exists()


@pytest.mark.django_db
class TestIntegrationViewSet:

    def test_list_integrations(self, authenticated_client, integration, team_with_lead, mock_auth_service):
        """Test listing integrations."""
        team, lead = team_with_lead
        integration.project.team = team
        integration.project.save()

        url = reverse("management:integration-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0

    def test_create_integration(self, authenticated_client, project, team_with_lead, mock_auth_service):
        """Test creating integration."""
        team, lead = team_with_lead
        project.team = team
        project.save()

        url = reverse("management:integration-list")
        data = {
            "project_id": str(project.id),
            "type": "slack",
            "config_data": {"webhook_url": "https://hooks.slack.com/test"},
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Integration.objects.filter(project=project, type="slack").exists()

    def test_retrieve_integration(self, authenticated_client, integration, team_with_lead, mock_auth_service):
        """Test retrieving integration details."""
        team, lead = team_with_lead
        integration.project.team = team
        integration.project.save()

        url = reverse("management:integration-detail", args=[integration.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == integration.type
        assert "project_name" in response.data

    def test_update_integration(self, authenticated_client, integration, team_with_lead, mock_auth_service):
        """Test updating integration."""
        team, lead = team_with_lead
        integration.project.team = team
        integration.project.save()

        url = reverse("management:integration-detail", args=[integration.id])
        data = {"is_active": False, "config_data": {"updated": "config"}}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        integration.refresh_from_db()
        assert integration.is_active is False

    def test_delete_integration(self, authenticated_client, integration, team_with_lead, mock_auth_service):
        """Test deleting integration."""
        team, lead = team_with_lead
        integration.project.team = team
        integration.project.save()

        url = reverse("management:integration-detail", args=[integration.id])

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
class TestGitHubIntegrationViewSet:

    def test_list_github_integrations(
        self,
        authenticated_client,
        github_integration,
        team_with_lead,
        mock_auth_service,
    ):
        """Test listing GitHub integrations."""
        team, lead = team_with_lead
        github_integration.project.team = team
        github_integration.project.save()

        url = reverse("management:githubintegration-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0

    def test_retrieve_github_integration(
        self,
        authenticated_client,
        github_integration,
        team_with_lead,
        mock_auth_service,
    ):
        """Test retrieving GitHub integration details."""
        team, lead = team_with_lead
        github_integration.project.team = team
        github_integration.project.save()

        url = reverse("management:githubintegration-detail", args=[github_integration.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["repository_owner"] == github_integration.repository_owner
        assert response.data["repository_name"] == github_integration.repository_name
        assert "repository_url" in response.data

    def test_github_integration_sync(
        self,
        authenticated_client,
        github_integration,
        team_with_lead,
        mock_auth_service,
    ):
        """Test triggering GitHub integration sync."""
        team, lead = team_with_lead
        github_integration.project.team = team
        github_integration.project.save()

        url = reverse("management:githubintegration-sync", args=[github_integration.id])

        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert "sync triggered successfully" in response.data["message"].lower()


@pytest.mark.django_db
class TestCodeCommitViewSet:

    def test_list_commits(self, authenticated_client, code_commit, team_with_lead, mock_auth_service):
        """Test listing code commits."""
        team, lead = team_with_lead
        code_commit.project.team = team
        code_commit.project.save()

        url = reverse("management:codecommit-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 0

    def test_retrieve_commit(self, authenticated_client, code_commit, team_with_lead, mock_auth_service):
        """Test retrieving commit details."""
        team, lead = team_with_lead
        code_commit.project.team = team
        code_commit.project.save()

        url = reverse("management:codecommit-detail", args=[code_commit.id])

        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["commit_hash"] == code_commit.commit_hash
        assert response.data["author_name"] == code_commit.author_name
        assert "net_changes" in response.data


@pytest.mark.django_db
class TestAPIHomeView:

    def test_api_home_get(self, api_client):
        """Test API home page GET request."""
        response = api_client.get("/")

        assert response.status_code == status.HTTP_200_OK
        assert response["content-type"] in ["text/html; charset=utf-8", "application/json"]

    def test_api_home_context(self, api_client):
        """Test API home page renders with correct context."""
        response = api_client.get("/")
        content = response.content.decode()

        assert "SyncScope Management Service" in content
        assert "1.0.0" in content
        assert "Team & Project Hub" in content


@pytest.mark.django_db
class TestPermissions:

    def test_admin_can_access_everything(self, admin_authenticated_client, team, mock_auth_service):
        """Test that admin users can access all resources."""
        # Override mock to return admin role
        mock_post, mock_get = mock_auth_service
        mock_post.return_value.json.return_value.update({"role": "admin"})

        url = reverse("management:team-detail", args=[team.id])
        response = admin_authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_denied(self, api_client, team):
        """Test that unauthenticated users are denied access."""
        url = reverse("management:team-detail", args=[team.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_member_access_denied(self, authenticated_client, team, mock_auth_service):
        """Test that non-team members are denied access to team resources."""
        # Mock user who is not a member of this team
        mock_post, mock_get = mock_auth_service
        mock_post.return_value.json.return_value.update(
            {"user_id": str(uuid.uuid4()), "role": "developer"}  # Different user ID
        )

        url = reverse("management:team-detail", args=[team.id])
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestErrorHandling:

    def test_invalid_uuid_format(self, authenticated_client, mock_auth_service):
        """Test handling of invalid UUID formats."""
        url = reverse("management:team-detail", args=["invalid-uuid"])
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_nonexistent_resource(self, authenticated_client, mock_auth_service):
        """Test handling of nonexistent resources."""
        url = reverse("management:team-detail", args=[str(uuid.uuid4())])
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_malformed_json_data(self, authenticated_client, mock_auth_service):
        """Test handling of malformed JSON data."""
        url = reverse("management:team-list")
        response = authenticated_client.post(url, data="invalid json", content_type="application/json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.management.authentication.requests.post")
    def test_auth_service_unavailable(self, mock_requests, api_client):
        """Test handling when auth service is unavailable."""
        mock_requests.side_effect = Exception("Service unavailable")

        api_client.credentials(HTTP_AUTHORIZATION="Bearer test-token")
        url = reverse("management:team-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAnalyticsIntegrationViews:
    """Test views created for analytics service integration."""

    def test_api_get_team_members_default_team(self, api_client):
        """Test getting default team members for analytics integration."""
        from django.urls import reverse

        url = reverse("api_team_members", args=["default"])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["team_id"] == "default"
        assert data["name"] == "Default Team"
        assert len(data["members"]) == 1
        assert data["member_count"] == 1
        assert data["members"][0]["username"] == "default_user"

    def test_api_get_team_members_with_params(self, api_client):
        """Test team members endpoint with query parameters."""
        from django.urls import reverse

        url = reverse("api_team_members", args=["default"])
        response = api_client.get(url, {"start_date": "2024-01-01", "end_date": "2024-12-31"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "team_id" in data
        assert "members" in data

    def test_get_git_events_team_endpoint_exists(self, api_client):
        """Test git events endpoint exists and is accessible."""
        from django.urls import reverse

        url = reverse("management:get_git_events_team")
        response = api_client.get(url)

        # Just test that the endpoint exists and returns a valid response
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_git_events_url_can_be_resolved(self):
        """Test git events URL can be resolved."""
        from django.urls import reverse

        # Just test that the URL can be resolved without error
        url = reverse("management:get_git_events_team")
        assert url is not None
        assert "/git-events/team/" in url


@pytest.mark.django_db
class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check_success(self, api_client):
        """Test successful health check."""
        from django.urls import reverse

        url = reverse("detailed_health_check")
        response = api_client.get(url)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data

    def test_simple_health_check(self, api_client):
        """Test simple health check endpoint."""
        from django.urls import reverse

        url = reverse("health_check")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "management-service"

    def test_readiness_check(self, api_client):
        """Test readiness check endpoint."""
        from django.urls import reverse

        url = reverse("readiness_check")
        response = api_client.get(url)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()
        assert "status" in data

    def test_liveness_check(self, api_client):
        """Test liveness check endpoint."""
        from django.urls import reverse

        url = reverse("liveness_check")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "management"

    @patch("apps.management.health.cache.set")
    @patch("apps.management.health.cache.get")
    def test_health_check_cache_failure(self, mock_get, mock_set, api_client):
        """Test health check with cache failure."""
        from django.urls import reverse

        mock_set.side_effect = Exception("Cache unavailable")
        mock_get.side_effect = Exception("Cache unavailable")

        url = reverse("detailed_health_check")
        response = api_client.get(url)

        # Should still return a response even if cache fails
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        data = response.json()
        assert "status" in data

    @patch("apps.management.health.DatabaseHealthCheck.is_healthy")
    def test_health_check_database_failure(self, mock_db_health, api_client):
        """Test health check with database failure."""
        from django.urls import reverse

        mock_db_health.return_value = False

        url = reverse("detailed_health_check")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "errors" in data

    @patch("apps.management.health.DatabaseHealthCheck.is_healthy")
    def test_readiness_check_database_failure(self, mock_db_health, api_client):
        """Test readiness check with database failure."""
        from django.urls import reverse

        mock_db_health.return_value = False

        url = reverse("readiness_check")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "not ready"


@pytest.mark.django_db
class TestProjectMemberViewSet:
    """Test ProjectMember API endpoints."""

    def test_list_project_members(self, authenticated_client, project, project_member, mock_user_data):
        """Test listing project members."""
        from apps.management.models import ProjectMember, TeamMember

        # Make authenticated user a team member so they can access project members
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        url = reverse("management:projectmember-list")
        response = authenticated_client.get(url, {"project": project.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("results", data)  # Handle both paginated and non-paginated responses
        assert len(results) >= 1
        assert any(str(pm["user_id"]) == str(project_member.user_id) for pm in results)

    def test_create_project_member_success(self, authenticated_client, project, team_member, mock_user_data):
        """Test creating a project member successfully."""
        from apps.management.models import ProjectMember, TeamMember

        # Make authenticated user a team lead so they can add project members
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})

        url = reverse("management:projectmember-list")
        data = {"project": str(project.id), "user_id": str(team_member.user_id), "role": "contributor"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert str(response_data["user_id"]) == str(team_member.user_id)
        assert response_data["role"] == "contributor"

    def test_create_project_member_not_team_member(self, authenticated_client, project, mock_user_data):
        """Test creating project member fails when user is not a team member."""
        import uuid

        url = reverse("management:projectmember-list")
        random_user_id = uuid.uuid4()
        data = {"project": str(project.id), "user_id": str(random_user_id), "role": "contributor"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_project_member_duplicate(self, authenticated_client, project, project_member):
        """Test creating duplicate project member fails."""
        url = reverse("management:projectmember-list")
        data = {"project": str(project.id), "user_id": str(project_member.user_id), "role": "owner"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_project_member(self, authenticated_client, project_member, mock_user_data):
        """Test retrieving a specific project member."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member so they can access project members
        TeamMember.objects.get_or_create(
            team=project_member.project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"}
        )

        url = reverse("management:projectmember-detail", kwargs={"pk": project_member.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert str(data["user_id"]) == str(project_member.user_id)
        assert data["role"] == project_member.role

    def test_update_project_member(self, authenticated_client, project_member, mock_user_data):
        """Test updating project member role."""
        from apps.management.models import ProjectMember, TeamMember

        # Make authenticated user a team lead so they can update project members
        TeamMember.objects.get_or_create(
            team=project_member.project.team, user_id=mock_user_data["user_id"], defaults={"role": "lead"}
        )

        url = reverse("management:projectmember-detail", kwargs={"pk": project_member.id})
        data = {"role": "viewer"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["role"] == "viewer"

    def test_delete_project_member(self, authenticated_client, project, team_member, mock_user_data):
        """Test deleting a project member."""
        from apps.management.models import ProjectMember, TeamMember

        # Make authenticated user a team lead so they can delete project members
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})

        # Create a project member to delete
        member = ProjectMember.objects.create(project=project, user_id=team_member.user_id, role="contributor")

        url = reverse("management:projectmember-detail", kwargs={"pk": member.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProjectMember.objects.filter(id=member.id).exists()


@pytest.mark.django_db
class TestGetUserProjectsEndpoint:
    """Test get_user_projects API endpoint."""

    def test_get_user_projects_with_direct_membership(self, authenticated_client, project, mock_user_data):
        """Test getting projects where user is a direct member."""
        # Create direct project membership for the authenticated user
        from apps.management.models import ProjectMember, TeamMember

        # First make authenticated user a team member
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})
        # Then make them a project member
        ProjectMember.objects.get_or_create(
            project=project, user_id=mock_user_data["user_id"], defaults={"role": "contributor"}
        )

        url = reverse("management:get_user_projects", kwargs={"user_id": mock_user_data["user_id"]})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) >= 1
        assert any(p["id"] == str(project.id) for p in data["projects"])
        assert str(data["user_id"]) == str(mock_user_data["user_id"])

    def test_get_user_projects_with_team_membership(self, authenticated_client, team, project, mock_user_data):
        """Test getting projects via team membership."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(team=team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        url = reverse("management:get_user_projects", kwargs={"user_id": mock_user_data["user_id"]})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) >= 1
        assert any(p["id"] == str(project.id) for p in data["projects"])

    def test_get_user_projects_no_projects(self, authenticated_client, mock_user_data):
        """Test getting projects for user with no project access."""
        # Use authenticated user's ID but don't add any memberships
        url = reverse("management:get_user_projects", kwargs={"user_id": mock_user_data["user_id"]})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) == 0
        assert data["total_projects"] == 0

    def test_get_user_projects_combines_both_sources(self, authenticated_client, team, project, mock_user_data):
        """Test that endpoint combines projects from both team and direct membership."""
        from apps.management.models import Project, ProjectMember, TeamMember

        # Make authenticated user a member of the first team
        TeamMember.objects.get_or_create(team=team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        # Create another project with another team
        other_team = team.__class__.objects.create(name="Other Team", company_id=team.company_id, created_by=team.created_by)
        other_project = Project.objects.create(name="Other Project", team=other_team)

        # Add authenticated user as team member of other team
        TeamMember.objects.create(team=other_team, user_id=mock_user_data["user_id"], role="developer")

        # Add authenticated user as direct project member of other project
        ProjectMember.objects.create(project=other_project, user_id=mock_user_data["user_id"], role="contributor")

        url = reverse("management:get_user_projects", kwargs={"user_id": mock_user_data["user_id"]})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["projects"]) >= 2
        project_ids = [p["id"] for p in data["projects"]]
        assert str(project.id) in project_ids
        assert str(other_project.id) in project_ids


@pytest.mark.django_db
class TestAdditionalViewCoverage:
    """Additional tests to improve view coverage."""

    def test_team_detail_view(self, authenticated_client, team):
        """Test team detail view."""
        url = reverse("management:team-detail", kwargs={"pk": team.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == team.name

    def test_team_update_view(self, authenticated_client, team):
        """Test team update view."""
        url = reverse("management:team-detail", kwargs={"pk": team.id})
        data = {"name": "Updated Team Name", "description": "Updated description"}
        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        updated_data = response.json()
        assert updated_data["name"] == "Updated Team Name"

    def test_team_delete_view(self, authenticated_client, company_id, mock_user_data):
        """Test team delete view."""
        from apps.management.models import Team

        # Create a team to delete
        team = Team.objects.create(name="Team to Delete", company_id=company_id, created_by=mock_user_data["user_id"])

        url = reverse("management:team-detail", kwargs={"pk": team.id})
        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Team.objects.filter(id=team.id).exists()

    def test_project_detail_view(self, authenticated_client, project, mock_user_data):
        """Test project detail view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        url = reverse("management:project-detail", kwargs={"pk": project.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == project.name

    def test_project_update_view(self, authenticated_client, project, mock_user_data):
        """Test project update view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team lead (required for project updates)
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})

        url = reverse("management:project-detail", kwargs={"pk": project.id})
        data = {"name": "Updated Project Name"}
        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        updated_data = response.json()
        assert updated_data["name"] == "Updated Project Name"

    def test_integration_list_view(self, authenticated_client, integration, mock_user_data):
        """Test integration list view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(
            team=integration.project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"}
        )

        url = reverse("management:integration-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("results", data)
        assert len(results) >= 0

    def test_integration_detail_view(self, authenticated_client, integration, mock_user_data):
        """Test integration detail view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(
            team=integration.project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"}
        )

        url = reverse("management:integration-detail", kwargs={"pk": integration.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == integration.type

    def test_github_integration_list_view(self, authenticated_client, github_integration, mock_user_data):
        """Test GitHub integration list view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(
            team=github_integration.project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"}
        )

        url = reverse("management:githubintegration-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("results", data)
        assert len(results) >= 0

    def test_commit_list_view(self, authenticated_client, code_commit, mock_user_data):
        """Test code commit list view."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(
            team=code_commit.project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"}
        )

        url = reverse("management:codecommit-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("results", data)
        assert len(results) >= 0

    def test_team_members_action_post_without_permission(self, authenticated_client, team):
        """Test adding team member without permission returns 403."""
        import uuid

        from apps.management.models import TeamMember

        # Don't make user a team lead, so they don't have permission
        url = reverse("management:team-members", kwargs={"pk": team.id})
        data = {"user_id": str(uuid.uuid4()), "role": "developer"}
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_team_members_action_post_invalid_data(self, authenticated_client, team, mock_user_data):
        """Test adding team member with invalid data returns 400."""
        from apps.management.models import TeamMember

        # Make user a team lead
        TeamMember.objects.get_or_create(team=team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})

        url = reverse("management:team-members", kwargs={"pk": team.id})
        data = {"user_id": "invalid-uuid", "role": "developer"}
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_project_members_action_get(self, authenticated_client, project, mock_user_data, project_member):
        """Test getting project members."""
        from apps.management.models import TeamMember

        # Make authenticated user a team member
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        url = reverse("management:project-members", kwargs={"pk": project.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_project_members_action_post_without_permission(self, authenticated_client, project, mock_user_data):
        """Test adding project member without permission returns 403."""
        import uuid

        from apps.management.models import TeamMember

        # Make user a team member but not a lead (so they don't have permission to manage)
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "developer"})

        url = reverse("management:project-members", kwargs={"pk": project.id})
        data = {"user_id": str(uuid.uuid4()), "role": "contributor"}
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_project_members_action_post_non_team_member(self, authenticated_client, project, mock_user_data):
        """Test adding non-team member to project returns 400."""
        import uuid

        from apps.management.models import TeamMember

        # Make user a team lead so they have permission
        TeamMember.objects.get_or_create(team=project.team, user_id=mock_user_data["user_id"], defaults={"role": "lead"})

        # Try to add a user who is not a team member
        url = reverse("management:project-members", kwargs={"pk": project.id})
        data = {"user_id": str(uuid.uuid4()), "role": "contributor"}
        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "team" in response.json()["error"].lower()


@pytest.mark.django_db
class TestOrganizationSettingsViewSet:

    def test_get_organization_settings_auto_create(self, authenticated_client, company_id, mock_user_data, mock_auth_service):
        """Test that organization settings are auto-created if they don't exist."""
        url = reverse("management:organizationsettings-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

        # Verify settings were created
        assert OrganizationSettings.objects.filter(company_id=company_id).exists()

    def test_get_organization_settings_existing(self, authenticated_client, company_id, mock_auth_service):
        """Test getting existing organization settings."""
        # Create settings first
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            deletion_protection_enabled=True,
            updated_by=mock_user_data["user_id"],
        )

        url = reverse("management:organizationsettings-list")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data[0]["company_id"] == str(company_id)
        assert response.data[0]["deletion_protection_enabled"] is True

    def test_get_organization_settings_unauthenticated(self, api_client):
        """Test that unauthenticated users cannot access settings."""
        url = reverse("management:organizationsettings-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_organization_settings(self, authenticated_client, company_id, mock_auth_service):
        """Test updating organization settings."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            deletion_protection_enabled=False,
            updated_by=mock_user_data["user_id"],
        )

        url = reverse("management:organizationsettings-detail", args=[settings.id])
        data = {
            "deletion_protection_enabled": True,
            "deletion_password": "NewPassword123!",
        }

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        settings.refresh_from_db()
        assert settings.deletion_protection_enabled is True
        assert settings.deletion_password_hash is not None

    def test_verify_deletion_password_success(self, authenticated_client, company_id, mock_auth_service):
        """Test successful password verification."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            deletion_protection_enabled=True,
            updated_by=mock_user_data["user_id"],
        )
        settings.set_deletion_password("ValidPass123!", validate_complexity=True)
        settings.save()

        url = reverse("management:organizationsettings-verify-deletion-password")
        data = {"password": "ValidPass123!"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is True

    def test_verify_deletion_password_failure(self, authenticated_client, company_id, mock_auth_service):
        """Test password verification with wrong password."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            deletion_protection_enabled=True,
            updated_by=mock_user_data["user_id"],
        )
        settings.set_deletion_password("ValidPass123!", validate_complexity=True)
        settings.save()

        url = reverse("management:organizationsettings-verify-deletion-password")
        data = {"password": "WrongPassword123!"}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["valid"] is False

        # Verify failed attempt was recorded
        settings.refresh_from_db()
        assert settings.failed_deletion_attempts == 1

    def test_reset_failed_attempts(self, authenticated_client, company_id, mock_auth_service):
        """Test resetting failed deletion attempts."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            failed_deletion_attempts=10,
            updated_by=mock_user_data["user_id"],
        )

        url = reverse("management:organizationsettings-reset-failed-attempts", args=[settings.id])
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        settings.refresh_from_db()
        assert settings.failed_deletion_attempts == 0
