import uuid
from unittest.mock import Mock, patch

import pytest
from rest_framework.test import APIRequestFactory

from apps.management.authentication import RemoteUserProxy
from apps.management.models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
    Team,
    TeamMember,
)
from apps.management.serializers import (
    CodeCommitSerializer,
    GitHubIntegrationSerializer,
    IntegrationCreateSerializer,
    IntegrationSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectSerializer,
    TeamCreateSerializer,
    TeamDetailSerializer,
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    TeamSerializer,
    TeamUpdateSerializer,
)


@pytest.mark.django_db
class TestTeamSerializer:

    def test_team_serialization(self, team):
        """Test team model serialization."""
        serializer = TeamSerializer(team)
        data = serializer.data

        assert data["name"] == team.name
        assert data["description"] == team.description
        assert str(data["company_id"]) == str(team.company_id)
        assert str(data["created_by"]) == str(team.created_by)
        assert "created_at" in data
        assert "updated_at" in data

    def test_team_validation_with_context(self, company_id, mock_user_data):
        """Test team validation with request context."""
        factory = APIRequestFactory()
        request = factory.post("/teams/")
        request.user = RemoteUserProxy(mock_user_data)

        serializer = TeamSerializer(
            data={"name": "Test Team", "description": "Test"},
            context={"request": request},
        )

        assert serializer.is_valid()
        validated_data = serializer.validated_data

        # Should automatically set created_by and company_id from user
        assert str(validated_data.get("created_by")) == str(mock_user_data["user_id"])
        assert str(validated_data.get("company_id")) == str(mock_user_data["company_id"])

    def test_team_validation_without_context(self):
        """Test team validation without request context."""
        serializer = TeamSerializer(data={"name": "Test Team", "description": "Test"})

        assert serializer.is_valid()
        validated_data = serializer.validated_data

        # Should have default values for required fields
        assert "created_by" in validated_data
        assert "company_id" in validated_data
        assert str(validated_data["created_by"]) == "550e8400-e29b-41d4-a716-446655440000"
        assert str(validated_data["company_id"]) == "550e8400-e29b-41d4-a716-446655440001"


@pytest.mark.django_db
class TestTeamDetailSerializer:

    def test_team_detail_serialization(self, team, team_member, project):
        """Test team detail serialization with counts."""
        project.team = team
        project.save()
        team_member.team = team
        team_member.save()

        serializer = TeamDetailSerializer(team)
        data = serializer.data

        assert data["name"] == team.name
        assert data["members_count"] == 1
        assert data["projects_count"] == 1

    def test_team_detail_empty_counts(self, team):
        """Test team detail serialization with zero counts."""
        serializer = TeamDetailSerializer(team)
        data = serializer.data

        assert data["members_count"] == 0
        assert data["projects_count"] == 0


@pytest.mark.django_db
class TestProjectSerializer:

    def test_project_serialization(self, project):
        """Test project model serialization."""
        serializer = ProjectSerializer(project)
        data = serializer.data

        assert data["name"] == project.name
        assert data["description"] == project.description
        assert data["team_name"] == project.team.name
        assert data["repository_url"] == project.repository_url
        assert data["url"] == project.url

    def test_project_team_validation_as_member(self, team, mock_user_data):
        """Test project team validation when user is team member."""
        # Create team member relationship
        TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"], role="developer")

        factory = APIRequestFactory()
        request = factory.post("/projects/")
        request.user = RemoteUserProxy(mock_user_data)

        serializer = ProjectSerializer(data={"name": "Test Project", "team": team.id}, context={"request": request})

        assert serializer.is_valid()

    def test_project_team_validation_as_admin(self, team, mock_admin_user_data):
        """Test project team validation when user is admin."""
        factory = APIRequestFactory()
        request = factory.post("/projects/")
        request.user = RemoteUserProxy(mock_admin_user_data)

        serializer = ProjectSerializer(data={"name": "Test Project", "team": team.id}, context={"request": request})

        assert serializer.is_valid()

    def test_project_team_validation_not_member(self, team, mock_user_data):
        """Test project team validation when user is not team member."""
        factory = APIRequestFactory()
        request = factory.post("/projects/")
        request.user = RemoteUserProxy(mock_user_data)

        serializer = ProjectSerializer(data={"name": "Test Project", "team": team.id}, context={"request": request})

        assert not serializer.is_valid()
        assert "team" in serializer.errors


@pytest.mark.django_db
class TestProjectDetailSerializer:

    def test_project_detail_serialization(self, project, integration, code_commit):
        """Test project detail serialization with related data."""
        integration.project = project
        integration.save()
        code_commit.project = project
        code_commit.save()

        serializer = ProjectDetailSerializer(project)
        data = serializer.data

        assert data["name"] == project.name
        assert data["integrations_count"] == 1
        assert data["commits_count"] == 1
        assert data["latest_commit"]["hash"] == code_commit.commit_hash[:8]
        assert data["latest_commit"]["message"] == code_commit.message
        assert data["latest_commit"]["author"] == code_commit.author_name

    def test_project_detail_no_commits(self, project):
        """Test project detail serialization with no commits."""
        serializer = ProjectDetailSerializer(project)
        data = serializer.data

        assert data["commits_count"] == 0
        assert data["latest_commit"] is None

    def test_project_detail_inactive_integrations(self, project, integration):
        """Test project detail only counts active integrations."""
        integration.project = project
        integration.is_active = False
        integration.save()

        serializer = ProjectDetailSerializer(project)
        data = serializer.data

        assert data["integrations_count"] == 0


@pytest.mark.django_db
class TestTeamMemberSerializer:

    @patch("apps.management.authentication.AuthServiceIntegration.get_user_by_id")
    def test_team_member_serialization(self, mock_get_user, team_member):
        """Test team member serialization with user data."""
        mock_get_user.return_value = {
            "email": "testuser@example.com",
            "first_name": "Test",
            "last_name": "User",
        }

        factory = APIRequestFactory()
        request = factory.get("/team-members/")
        request.auth = "test-token"

        serializer = TeamMemberSerializer(team_member, context={"request": request})
        data = serializer.data

        assert str(data["user_id"]) == str(team_member.user_id)
        assert data["role"] == team_member.role
        assert data["team_name"] == team_member.team.name
        assert data["user_email"] == "testuser@example.com"
        assert data["user_name"] == "Test User"

    @patch("apps.management.authentication.AuthServiceIntegration.get_user_by_id")
    def test_team_member_serialization_no_user_data(self, mock_get_user, team_member):
        """Test team member serialization when user data is not available."""
        mock_get_user.return_value = None

        factory = APIRequestFactory()
        request = factory.get("/team-members/")
        request.auth = "test-token"

        serializer = TeamMemberSerializer(team_member, context={"request": request})
        data = serializer.data

        assert data["user_email"] == "Unknown"
        assert data["user_name"] == "Unknown User"

    def test_team_member_validation_duplicate(self, team, mock_user_data):
        """Test team member validation prevents duplicates."""
        # Create existing member
        TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"], role="developer")

        serializer = TeamMemberSerializer(data={"team": team.id, "user_id": mock_user_data["user_id"], "role": "lead"})

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_team_member_validation_permissions(self, team, mock_user_data):
        """Test team member validation checks permissions."""
        factory = APIRequestFactory()
        request = factory.post("/team-members/")
        request.user = RemoteUserProxy(mock_user_data)  # Not admin, not team lead

        serializer = TeamMemberSerializer(
            data={"team": team.id, "user_id": str(uuid.uuid4()), "role": "developer"},
            context={"request": request},
        )

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors


@pytest.mark.django_db
class TestIntegrationSerializer:

    def test_integration_serialization(self, integration):
        """Test integration model serialization."""
        serializer = IntegrationSerializer(integration)
        data = serializer.data

        assert data["type"] == integration.type
        assert data["config_data"] == integration.config_data
        assert data["is_active"] == integration.is_active
        assert data["project_name"] == integration.project.name

    def test_integration_config_validation_github(self, project):
        """Test integration config validation for GitHub type."""
        serializer = IntegrationSerializer(
            data={
                "project": project.id,
                "type": "github",
                "config_data": {
                    "repository_owner": "testuser",
                    "repository_name": "test-repo",
                },
            }
        )

        assert serializer.is_valid()

    def test_integration_config_validation_github_missing_fields(self):
        """Test integration config validation fails for GitHub with missing fields."""
        serializer = IntegrationSerializer(
            data={
                "type": "github",
                "config_data": {
                    "repository_owner": "testuser"
                    # Missing repository_name
                },
            }
        )

        assert not serializer.is_valid()
        assert "config_data" in serializer.errors

    def test_integration_config_validation_slack(self, project):
        """Test integration config validation for Slack type."""
        serializer = IntegrationSerializer(
            data={
                "project": project.id,
                "type": "slack",
                "config_data": {"webhook_url": "https://hooks.slack.com/test"},
            }
        )

        assert serializer.is_valid()

    def test_integration_config_validation_slack_missing_fields(self):
        """Test integration config validation fails for Slack with missing fields."""
        serializer = IntegrationSerializer(data={"type": "slack", "config_data": {}})

        assert not serializer.is_valid()
        assert "config_data" in serializer.errors


@pytest.mark.django_db
class TestGitHubIntegrationSerializer:

    def test_github_integration_serialization(self, github_integration):
        """Test GitHub integration model serialization."""
        serializer = GitHubIntegrationSerializer(github_integration)
        data = serializer.data

        assert data["repository_owner"] == github_integration.repository_owner
        assert data["repository_name"] == github_integration.repository_name
        assert data["repository_url"] == github_integration.repository_url
        assert data["is_active"] == github_integration.is_active
        assert data["project_name"] == github_integration.project.name

    def test_github_integration_validation_duplicate(self, project):
        """Test GitHub integration validation prevents duplicates."""
        # Create existing integration
        GitHubIntegration.objects.create(
            project=project,
            repository_owner="testuser",
            repository_name="test-repo",
            access_token="token1",
        )

        serializer = GitHubIntegrationSerializer(
            data={
                "project": project.id,
                "repository_owner": "testuser",
                "repository_name": "test-repo",
                "access_token": "token2",
            }
        )

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors


@pytest.mark.django_db
class TestCodeCommitSerializer:

    def test_code_commit_serialization(self, code_commit):
        """Test code commit model serialization."""
        serializer = CodeCommitSerializer(code_commit)
        data = serializer.data

        assert data["commit_hash"] == code_commit.commit_hash
        assert data["author_email"] == code_commit.author_email
        assert data["author_name"] == code_commit.author_name
        assert data["message"] == code_commit.message
        assert data["branch"] == code_commit.branch
        assert data["files_changed"] == code_commit.files_changed
        assert data["insertions"] == code_commit.insertions
        assert data["deletions"] == code_commit.deletions
        assert data["net_changes"] == str(code_commit.net_changes)
        assert data["project_name"] == code_commit.project.name


@pytest.mark.django_db
class TestRequestResponseSerializers:

    def test_team_create_serializer(self):
        """Test team creation request serializer."""
        serializer = TeamCreateSerializer(data={"name": "New Team", "description": "Team description"})

        assert serializer.is_valid()
        assert serializer.validated_data["name"] == "New Team"
        assert serializer.validated_data["description"] == "Team description"

    def test_team_create_serializer_required_fields(self):
        """Test team creation serializer required fields."""
        serializer = TeamCreateSerializer(data={})

        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_team_update_serializer(self):
        """Test team update request serializer."""
        serializer = TeamUpdateSerializer(data={"name": "Updated Name", "description": "Updated description"})

        assert serializer.is_valid()

    def test_team_update_serializer_optional_fields(self):
        """Test team update serializer with optional fields."""
        serializer = TeamUpdateSerializer(data={})

        assert serializer.is_valid()  # All fields are optional

    def test_project_create_serializer(self, team):
        """Test project creation request serializer."""
        serializer = ProjectCreateSerializer(
            data={
                "name": "New Project",
                "description": "Project description",
                "team_id": str(team.id),
                "repository_url": "https://github.com/test/repo",
                "url": "https://project.com",
            }
        )

        assert serializer.is_valid()
        assert serializer.validated_data["name"] == "New Project"
        assert serializer.validated_data["team_id"] == team.id

    def test_project_create_serializer_required_fields(self):
        """Test project creation serializer required fields."""
        serializer = ProjectCreateSerializer(data={})

        assert not serializer.is_valid()
        assert "name" in serializer.errors
        assert "team_id" in serializer.errors

    def test_team_member_create_serializer(self):
        """Test team member creation request serializer."""
        user_id = uuid.uuid4()
        serializer = TeamMemberCreateSerializer(data={"user_id": str(user_id), "role": "developer"})

        assert serializer.is_valid()
        assert serializer.validated_data["user_id"] == user_id
        assert serializer.validated_data["role"] == "developer"

    def test_team_member_create_serializer_default_role(self):
        """Test team member creation serializer default role."""
        user_id = uuid.uuid4()
        serializer = TeamMemberCreateSerializer(data={"user_id": str(user_id)})

        assert serializer.is_valid()
        assert serializer.validated_data["role"] == "developer"

    def test_integration_create_serializer(self, project):
        """Test integration creation request serializer."""
        serializer = IntegrationCreateSerializer(
            data={
                "project_id": str(project.id),
                "type": "github",
                "config_data": {"repository_owner": "testuser", "repository_name": "test-repo"},
            }
        )

        assert serializer.is_valid()
        assert serializer.validated_data["project_id"] == project.id
        assert serializer.validated_data["type"] == "github"
        assert serializer.validated_data["config_data"]["repository_owner"] == "testuser"

    def test_integration_create_serializer_required_fields(self):
        """Test integration creation serializer required fields."""
        serializer = IntegrationCreateSerializer(data={})

        assert not serializer.is_valid()
        assert "project_id" in serializer.errors
        assert "type" in serializer.errors
        assert "config_data" in serializer.errors
