import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.management.models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    OrganizationSettings,
    Project,
    ProjectMember,
    Team,
    TeamMember,
)


@pytest.mark.django_db
class TestTeamModel:

    def test_create_team_success(self, company_id, mock_user_data):
        """Test successful team creation."""
        team = Team.objects.create(
            name="Test Team",
            description="Test Description",
            company_id=company_id,
            created_by=mock_user_data["user_id"],
        )

        assert team.name == "Test Team"
        assert team.description == "Test Description"
        assert team.company_id == company_id
        assert team.created_by == mock_user_data["user_id"]
        assert team.id is not None
        assert team.created_at is not None
        assert team.updated_at is not None

    def test_team_str_representation(self, team):
        """Test team string representation."""
        assert str(team) == team.name

    def test_team_ordering(self, company_id, mock_user_data):
        """Test that teams are ordered by creation date (newest first)."""
        team1 = Team.objects.create(
            name="First Team",
            company_id=company_id,
            created_by=mock_user_data["user_id"],
        )

        team2 = Team.objects.create(
            name="Second Team",
            company_id=company_id,
            created_by=mock_user_data["user_id"],
        )

        teams = list(Team.objects.all())
        assert teams[0] == team2  # Newest first
        assert teams[1] == team1

    def test_team_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(IntegrityError):
            Team.objects.create(name="Test Team")  # Missing required fields


@pytest.mark.django_db
class TestProjectModel:

    def test_create_project_success(self, team):
        """Test successful project creation."""
        project = Project.objects.create(
            name="Test Project",
            description="Test Description",
            team=team,
            repository_url="https://github.com/test/repo",
            url="https://test.com",
        )

        assert project.name == "Test Project"
        assert project.description == "Test Description"
        assert project.team == team
        assert project.repository_url == "https://github.com/test/repo"
        assert project.url == "https://test.com"
        assert project.id is not None
        assert project.created_at is not None
        assert project.updated_at is not None

    def test_project_str_representation(self, project):
        """Test project string representation."""
        expected = f"{project.name} - {project.team.name}"
        assert str(project) == expected

    def test_project_team_relationship(self, team):
        """Test project-team relationship."""
        project = Project.objects.create(name="Test Project", team=team)

        assert project.team == team
        assert project in team.projects.all()

    def test_project_cascade_delete(self, team):
        """Test that projects are deleted when team is deleted."""
        project = Project.objects.create(name="Test Project", team=team)

        team.delete()
        assert not Project.objects.filter(id=project.id).exists()


@pytest.mark.django_db
class TestTeamMemberModel:

    def test_create_team_member_success(self, team, mock_user_data):
        """Test successful team member creation."""
        member = TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"], role="developer")

        assert member.team == team
        assert member.user_id == mock_user_data["user_id"]
        assert member.role == "developer"
        assert member.id is not None
        assert member.joined_at is not None
        assert member.created_at is not None
        assert member.updated_at is not None

    def test_team_member_str_representation(self, team_member):
        """Test team member string representation."""
        expected = f"User {team_member.user_id} - {team_member.team.name} ({team_member.role})"
        assert str(team_member) == expected

    def test_team_member_unique_constraint(self, team, mock_user_data):
        """Test that a user can only be a member of a team once."""
        TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"], role="developer")

        # Attempting to add the same user again should fail
        with pytest.raises(IntegrityError):
            TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"], role="lead")

    def test_team_member_role_choices(self, team, mock_user_data):
        """Test valid role choices."""
        valid_roles = [
            "lead",
            "developer",
            "senior_developer",
            "junior_developer",
            "intern",
            "designer",
            "qa",
        ]

        for role in valid_roles:
            member = TeamMember.objects.create(team=team, user_id=uuid.uuid4(), role=role)
            assert member.role == role

    def test_default_role(self, team, mock_user_data):
        """Test that default role is 'developer'."""
        member = TeamMember.objects.create(team=team, user_id=mock_user_data["user_id"])
        assert member.role == "developer"


@pytest.mark.django_db
class TestProjectMemberModel:

    def test_create_project_member_success(self, project, team_member):
        """Test successful project member creation."""
        member = ProjectMember.objects.create(project=project, user_id=team_member.user_id, role="contributor")

        assert member.project == project
        assert str(member.user_id) == str(team_member.user_id)
        assert member.role == "contributor"
        assert member.id is not None
        assert member.joined_at is not None
        assert member.created_at is not None
        assert member.updated_at is not None

    def test_project_member_str_representation(self, project_member):
        """Test project member string representation."""
        expected = f"User {project_member.user_id} - {project_member.project.name} ({project_member.role})"
        assert str(project_member) == expected

    def test_project_member_unique_constraint(self, project, team_member):
        """Test that a user can only be a member of a project once."""
        ProjectMember.objects.create(project=project, user_id=team_member.user_id, role="contributor")

        # Attempting to add the same user again should fail (ValidationError due to full_clean validation)
        with pytest.raises(ValidationError):
            ProjectMember.objects.create(project=project, user_id=team_member.user_id, role="owner")

    def test_project_member_role_choices(self, project, team):
        """Test valid role choices."""
        valid_roles = ["owner", "contributor", "viewer"]

        for role in valid_roles:
            # Create a team member first (required for project membership)
            user_id = uuid.uuid4()
            TeamMember.objects.create(team=team, user_id=user_id, role="developer")

            # Now create project member
            member = ProjectMember.objects.create(project=project, user_id=user_id, role=role)
            assert member.role == role

    def test_default_role(self, project, team_member):
        """Test that default role is 'contributor'."""
        member = ProjectMember.objects.create(project=project, user_id=team_member.user_id)
        assert member.role == "contributor"

    def test_project_member_requires_team_membership(self, project, mock_user_data):
        """Test that user must be a team member before joining project."""
        # Try to create project member without team membership
        random_user_id = uuid.uuid4()

        # This should raise ValidationError because user is not a team member
        with pytest.raises(ValidationError):
            member = ProjectMember(project=project, user_id=random_user_id, role="contributor")
            member.full_clean()  # This triggers the validation

    def test_project_member_team_validation_on_save(self, project):
        """Test that validation is enforced on save."""
        # Try to create project member without team membership
        random_user_id = uuid.uuid4()

        # This should raise ValidationError because user is not a team member
        with pytest.raises(ValidationError):
            ProjectMember.objects.create(project=project, user_id=random_user_id, role="contributor")

    def test_project_member_cascade_delete(self, project, team_member):
        """Test that project members are deleted when project is deleted."""
        member = ProjectMember.objects.create(project=project, user_id=team_member.user_id, role="contributor")

        project.delete()
        assert not ProjectMember.objects.filter(id=member.id).exists()

    def test_project_relationship(self, project_member):
        """Test project-member relationship."""
        assert project_member in project_member.project.members.all()


@pytest.mark.django_db
class TestIntegrationModel:

    def test_create_integration_success(self, project):
        """Test successful integration creation."""
        integration = Integration.objects.create(
            project=project,
            type="github",
            config_data={"repo": "test/repo"},
            is_active=True,
        )

        assert integration.project == project
        assert integration.type == "github"
        assert integration.config_data == {"repo": "test/repo"}
        assert integration.is_active is True
        assert integration.id is not None
        assert integration.created_at is not None
        assert integration.updated_at is not None

    def test_integration_str_representation(self, integration):
        """Test integration string representation."""
        expected = f"{integration.project.name} - {integration.get_type_display()}"
        assert str(integration) == expected

    def test_integration_default_config_data(self, project):
        """Test that config_data defaults to empty dict."""
        integration = Integration.objects.create(project=project, type="slack")
        assert integration.config_data == {}

    def test_integration_default_is_active(self, project):
        """Test that is_active defaults to True."""
        integration = Integration.objects.create(project=project, type="jira")
        assert integration.is_active is True

    def test_integration_type_choices(self, project):
        """Test valid integration type choices."""
        valid_types = [
            "github",
            "gitlab",
            "jira",
            "slack",
            "discord",
            "teams",
            "trello",
            "asana",
            "jenkins",
            "circleci",
            "custom",
        ]

        for int_type in valid_types:
            integration = Integration.objects.create(project=project, type=int_type)
            assert integration.type == int_type


@pytest.mark.django_db
class TestGitHubIntegrationModel:

    def test_create_github_integration_success(self, project):
        """Test successful GitHub integration creation."""
        github_integration = GitHubIntegration.objects.create(
            project=project,
            repository_owner="testuser",
            repository_name="test-repo",
            access_token="test-token",
            is_active=True,
        )

        assert github_integration.project == project
        assert github_integration.repository_owner == "testuser"
        assert github_integration.repository_name == "test-repo"
        assert github_integration.access_token == "test-token"
        assert github_integration.is_active is True
        assert github_integration.id is not None
        assert github_integration.created_at is not None
        assert github_integration.updated_at is not None

    def test_github_integration_str_representation(self, github_integration):
        """Test GitHub integration string representation."""
        expected = (
            f"{github_integration.repository_owner}/{github_integration.repository_name} - {github_integration.project.name}"
        )
        assert str(github_integration) == expected

    def test_github_integration_repository_url_property(self, github_integration):
        """Test repository_url property."""
        expected = f"https://github.com/{github_integration.repository_owner}/{github_integration.repository_name}"
        assert github_integration.repository_url == expected

    def test_github_integration_unique_constraint(self, project):
        """Test unique constraint on project/repo combination."""
        GitHubIntegration.objects.create(
            project=project,
            repository_owner="testuser",
            repository_name="test-repo",
            access_token="token1",
        )

        # Creating duplicate should fail
        with pytest.raises(IntegrityError):
            GitHubIntegration.objects.create(
                project=project,
                repository_owner="testuser",
                repository_name="test-repo",
                access_token="token2",
            )

    def test_github_integration_default_is_active(self, project):
        """Test that is_active defaults to True."""
        integration = GitHubIntegration.objects.create(
            project=project,
            repository_owner="user",
            repository_name="repo",
            access_token="token",
        )
        assert integration.is_active is True


@pytest.mark.django_db
class TestCodeCommitModel:

    def test_create_code_commit_success(self, project):
        """Test successful code commit creation."""
        commit = CodeCommit.objects.create(
            project=project,
            commit_hash="abc123def456",
            author_email="dev@example.com",
            author_name="Test Developer",
            message="Test commit",
            branch="main",
            timestamp=timezone.now(),
            files_changed=3,
            insertions=25,
            deletions=10,
        )

        assert commit.project == project
        assert commit.commit_hash == "abc123def456"
        assert commit.author_email == "dev@example.com"
        assert commit.author_name == "Test Developer"
        assert commit.message == "Test commit"
        assert commit.branch == "main"
        assert commit.files_changed == 3
        assert commit.insertions == 25
        assert commit.deletions == 10
        assert commit.id is not None
        assert commit.created_at is not None

    def test_code_commit_str_representation(self, code_commit):
        """Test code commit string representation."""
        expected = f"{code_commit.commit_hash[:8]} - {code_commit.project.name}"
        assert str(code_commit) == expected

    def test_code_commit_net_changes_property(self, code_commit):
        """Test net_changes property calculation."""
        # code_commit fixture has 25 insertions and 10 deletions
        assert code_commit.net_changes == 15

    def test_code_commit_unique_constraint(self, project):
        """Test unique constraint on project/commit_hash combination."""
        CodeCommit.objects.create(
            project=project,
            commit_hash="unique123",
            author_email="dev@example.com",
            author_name="Developer",
            message="First commit",
            timestamp=timezone.now(),
        )

        # Creating duplicate should fail
        with pytest.raises(IntegrityError):
            CodeCommit.objects.create(
                project=project,
                commit_hash="unique123",
                author_email="dev2@example.com",
                author_name="Other Developer",
                message="Second commit",
                timestamp=timezone.now(),
            )

    def test_code_commit_default_values(self, project):
        """Test default values for optional fields."""
        commit = CodeCommit.objects.create(
            project=project,
            commit_hash="test123",
            author_email="dev@example.com",
            author_name="Developer",
            message="Test",
            timestamp=timezone.now(),
        )

        assert commit.branch == "main"
        assert commit.files_changed == 0
        assert commit.insertions == 0
        assert commit.deletions == 0

    def test_code_commit_ordering(self, project):
        """Test that commits are ordered by timestamp (newest first)."""
        now = timezone.now()

        commit1 = CodeCommit.objects.create(
            project=project,
            commit_hash="first123",
            author_email="dev@example.com",
            author_name="Developer",
            message="First commit",
            timestamp=now - timedelta(hours=1),
        )

        commit2 = CodeCommit.objects.create(
            project=project,
            commit_hash="second123",
            author_email="dev@example.com",
            author_name="Developer",
            message="Second commit",
            timestamp=now,
        )

        commits = list(CodeCommit.objects.all())
        assert commits[0] == commit2  # Newest first
        assert commits[1] == commit1


@pytest.mark.django_db
class TestOrganizationSettingsModel:

    def test_create_organization_settings_success(self, company_id, mock_user_data):
        """Test successful organization settings creation."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            deletion_protection_enabled=True,
            updated_by=mock_user_data["user_id"],
        )

        assert settings.company_id == company_id
        assert settings.company_name == "Test Company"
        assert settings.deletion_protection_enabled is True
        # When protection is enabled, default password is auto-set
        assert settings.deletion_password_hash is not None
        assert settings.failed_deletion_attempts == 0
        assert settings.id is not None
        assert settings.created_at is not None
        assert settings.updated_at is not None

    def test_organization_settings_str_representation(self, company_id, mock_user_data):
        """Test organization settings string representation."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )
        expected = f"Settings for Test Company"
        assert str(settings) == expected

    def test_organization_settings_unique_company(self, company_id, mock_user_data):
        """Test that only one settings object can exist per company."""
        OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        # Creating duplicate should fail
        with pytest.raises(IntegrityError):
            OrganizationSettings.objects.create(
                company_id=company_id,
                company_name="Test Company",
                updated_by=mock_user_data["user_id"],
            )

    def test_set_deletion_password_with_validation(self, company_id, mock_user_data):
        """Test setting deletion password with complexity validation."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        # Valid password
        settings.set_deletion_password("ValidPass123!", validate_complexity=True)
        assert settings.deletion_password_hash is not None
        # Test environment uses MD5 hasher for speed
        assert "$" in settings.deletion_password_hash  # Verify it's hashed

    def test_set_deletion_password_without_validation(self, company_id, mock_user_data):
        """Test setting deletion password without complexity validation."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        # Simple password (would fail validation)
        settings.set_deletion_password("simple", validate_complexity=False)
        assert settings.deletion_password_hash is not None

    def test_set_deletion_password_validation_too_short(self, company_id, mock_user_data):
        """Test password validation fails for passwords less than 8 characters."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        with pytest.raises(ValidationError, match="at least 8 characters"):
            settings.set_deletion_password("Short1!", validate_complexity=True)

    def test_set_deletion_password_validation_no_uppercase(self, company_id, mock_user_data):
        """Test password validation fails without uppercase letter."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        with pytest.raises(ValidationError, match="at least one uppercase letter"):
            settings.set_deletion_password("lowercase123!", validate_complexity=True)

    def test_set_deletion_password_validation_no_number(self, company_id, mock_user_data):
        """Test password validation fails without number."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        with pytest.raises(ValidationError, match="at least one number"):
            settings.set_deletion_password("NoNumbers!", validate_complexity=True)

    def test_set_deletion_password_validation_no_special(self, company_id, mock_user_data):
        """Test password validation fails without special character."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        with pytest.raises(ValidationError, match="at least one special character"):
            settings.set_deletion_password("NoSpecial123", validate_complexity=True)

    def test_verify_deletion_password_success(self, company_id, mock_user_data):
        """Test successful password verification."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        password = "ValidPass123!"
        settings.set_deletion_password(password, validate_complexity=True)
        settings.save()

        assert settings.verify_deletion_password(password) is True

    def test_verify_deletion_password_failure(self, company_id, mock_user_data):
        """Test password verification fails with wrong password."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        settings.set_deletion_password("ValidPass123!", validate_complexity=True)
        settings.save()

        assert settings.verify_deletion_password("WrongPassword123!") is False

    def test_verify_deletion_password_no_hash(self, company_id, mock_user_data):
        """Test password verification returns False when no hash is set."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        assert settings.verify_deletion_password("AnyPassword123!") is False

    def test_get_default_password(self, company_id, mock_user_data):
        """Test getting default password (company name lowercase)."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        assert settings.get_default_password() == "test company"

    def test_get_default_password_no_company_name(self, company_id, mock_user_data):
        """Test default password when company name is not set."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="",
            updated_by=mock_user_data["user_id"],
        )

        assert settings.get_default_password() == ""  # Returns empty string when no name

    def test_record_failed_attempt(self, company_id, mock_user_data):
        """Test recording failed deletion attempts."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        assert settings.failed_deletion_attempts == 0

        settings.record_failed_attempt("user@example.com")
        assert settings.failed_deletion_attempts == 1

        settings.record_failed_attempt("user@example.com")
        assert settings.failed_deletion_attempts == 2

    def test_reset_failed_attempts(self, company_id, mock_user_data):
        """Test resetting failed deletion attempts."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            failed_deletion_attempts=5,
            updated_by=mock_user_data["user_id"],
        )

        settings.reset_failed_attempts()
        assert settings.failed_deletion_attempts == 0

    def test_default_values(self, company_id, mock_user_data):
        """Test default values for organization settings."""
        settings = OrganizationSettings.objects.create(
            company_id=company_id,
            company_name="Test Company",
            updated_by=mock_user_data["user_id"],
        )

        assert settings.deletion_protection_enabled is False
        assert settings.deletion_password_hash is None
        assert settings.failed_deletion_attempts == 0
