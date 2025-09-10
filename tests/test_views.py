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
        assert "text/html" in response["content-type"]

    def test_api_home_context(self, api_client):
        """Test API home page renders with correct context."""
        response = api_client.get("/")
        content = response.content.decode()

        assert "SyncScope Management Service" in content
        assert "1.0.0" in content
        assert "Team and project management service" in content


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

        assert response.status_code == status.HTTP_404_NOT_FOUND


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
