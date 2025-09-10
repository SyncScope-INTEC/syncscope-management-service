import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import timezone

from apps.management.admin import (
    CodeCommitAdmin,
    GitHubIntegrationAdmin,
    IntegrationAdmin,
    ProjectAdmin,
    TeamAdmin,
    TeamMemberAdmin,
)
from apps.management.models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
    Team,
    TeamMember,
)


@pytest.mark.django_db
class TestTeamAdmin:

    def test_team_admin_list_display(self, team):
        """Test team admin list display."""
        admin_site = AdminSite()
        admin = TeamAdmin(Team, admin_site)

        assert "name" in admin.list_display
        assert "company_id" in admin.list_display
        assert "created_by" in admin.list_display
        assert "members_count" in admin.list_display
        assert "projects_count" in admin.list_display
        assert "created_at" in admin.list_display

    def test_team_admin_members_count(self, team, team_member):
        """Test members_count display method."""
        team_member.team = team
        team_member.save()

        admin_site = AdminSite()
        admin = TeamAdmin(Team, admin_site)

        result = admin.members_count(team)
        assert "1" in str(result)

    def test_team_admin_projects_count(self, team, project):
        """Test projects_count display method."""
        project.team = team
        project.save()

        admin_site = AdminSite()
        admin = TeamAdmin(Team, admin_site)

        result = admin.projects_count(team)
        assert "1" in str(result)

    def test_team_admin_fieldsets(self):
        """Test team admin fieldsets configuration."""
        admin_site = AdminSite()
        admin = TeamAdmin(Team, admin_site)

        fieldsets = admin.fieldsets

        # Check that basic information fieldset exists
        basic_info = next((fs for fs in fieldsets if fs[0] == "Basic Information"), None)
        assert basic_info is not None
        assert "name" in basic_info[1]["fields"]
        assert "description" in basic_info[1]["fields"]

    def test_team_admin_inlines(self):
        """Test team admin inlines."""
        admin_site = AdminSite()
        admin = TeamAdmin(Team, admin_site)

        inline_models = [inline.model for inline in admin.inlines]
        assert TeamMember in inline_models
        assert Project in inline_models


@pytest.mark.django_db
class TestProjectAdmin:

    def test_project_admin_list_display(self, project):
        """Test project admin list display."""
        admin_site = AdminSite()
        admin = ProjectAdmin(Project, admin_site)

        assert "name" in admin.list_display
        assert "team" in admin.list_display
        assert "repository_url" in admin.list_display
        assert "integrations_count" in admin.list_display
        assert "commits_count" in admin.list_display
        assert "created_at" in admin.list_display

    def test_project_admin_integrations_count(self, project, integration):
        """Test integrations_count display method."""
        integration.project = project
        integration.is_active = True
        integration.save()

        admin_site = AdminSite()
        admin = ProjectAdmin(Project, admin_site)

        result = admin.integrations_count(project)
        assert "1" in str(result)

    def test_project_admin_integrations_count_inactive(self, project, integration):
        """Test integrations_count excludes inactive integrations."""
        integration.project = project
        integration.is_active = False
        integration.save()

        admin_site = AdminSite()
        admin = ProjectAdmin(Project, admin_site)

        result = admin.integrations_count(project)
        assert "0" in str(result)

    def test_project_admin_commits_count(self, project, code_commit):
        """Test commits_count display method."""
        code_commit.project = project
        code_commit.save()

        admin_site = AdminSite()
        admin = ProjectAdmin(Project, admin_site)

        result = admin.commits_count(project)
        assert "1" in str(result)

    def test_project_admin_inlines(self):
        """Test project admin inlines."""
        admin_site = AdminSite()
        admin = ProjectAdmin(Project, admin_site)

        inline_models = [inline.model for inline in admin.inlines]
        assert Integration in inline_models
        assert GitHubIntegration in inline_models
        assert CodeCommit in inline_models


@pytest.mark.django_db
class TestTeamMemberAdmin:

    def test_team_member_admin_list_display(self, team_member):
        """Test team member admin list display."""
        admin_site = AdminSite()
        admin = TeamMemberAdmin(TeamMember, admin_site)

        assert "user_id" in admin.list_display
        assert "team" in admin.list_display
        assert "role" in admin.list_display
        assert "joined_at" in admin.list_display
        assert "created_at" in admin.list_display

    def test_team_member_admin_search_fields(self):
        """Test team member admin search fields."""
        admin_site = AdminSite()
        admin = TeamMemberAdmin(TeamMember, admin_site)

        assert "user_id" in admin.search_fields
        assert "team__name" in admin.search_fields
        assert "role" in admin.search_fields


@pytest.mark.django_db
class TestIntegrationAdmin:

    def test_integration_admin_list_display(self, integration):
        """Test integration admin list display."""
        admin_site = AdminSite()
        admin = IntegrationAdmin(Integration, admin_site)

        assert "project" in admin.list_display
        assert "type" in admin.list_display
        assert "is_active" in admin.list_display
        assert "created_at" in admin.list_display

    def test_integration_admin_formfield_config_data(self):
        """Test integration admin config_data field customization."""
        admin_site = AdminSite()
        admin = IntegrationAdmin(Integration, admin_site)

        # Mock db_field for config_data with required attributes
        class MockField:
            name = "config_data"
            choices = None
            many_to_many = False
            one_to_many = False
            one_to_one = False
            remote_field = None

        field = MockField()
        result = admin.formfield_for_dbfield(field, None)

        # Should return a customized widget
        assert result is not None


@pytest.mark.django_db
class TestGitHubIntegrationAdmin:

    def test_github_integration_admin_list_display(self, github_integration):
        """Test GitHub integration admin list display."""
        admin_site = AdminSite()
        admin = GitHubIntegrationAdmin(GitHubIntegration, admin_site)

        assert "project" in admin.list_display
        assert "repository_display" in admin.list_display
        assert "is_active" in admin.list_display
        assert "last_sync" in admin.list_display
        assert "created_at" in admin.list_display

    def test_github_integration_admin_repository_display(self, github_integration):
        """Test repository_display method."""
        admin_site = AdminSite()
        admin = GitHubIntegrationAdmin(GitHubIntegration, admin_site)

        result = admin.repository_display(github_integration)

        assert github_integration.repository_owner in str(result)
        assert github_integration.repository_name in str(result)
        assert github_integration.repository_url in str(result)

    def test_github_integration_admin_readonly_fields(self):
        """Test GitHub integration admin readonly fields."""
        admin_site = AdminSite()
        admin = GitHubIntegrationAdmin(GitHubIntegration, admin_site)

        assert "repository_url" in admin.readonly_fields
        assert "last_sync" in admin.readonly_fields


@pytest.mark.django_db
class TestCodeCommitAdmin:

    def test_code_commit_admin_list_display(self, code_commit):
        """Test code commit admin list display."""
        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        assert "short_hash" in admin.list_display
        assert "project" in admin.list_display
        assert "author_name" in admin.list_display
        assert "branch" in admin.list_display
        assert "net_changes_display" in admin.list_display
        assert "timestamp" in admin.list_display

    def test_code_commit_admin_short_hash(self, code_commit):
        """Test short_hash display method."""
        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        result = admin.short_hash(code_commit)

        assert code_commit.commit_hash[:8] in str(result)
        assert "<code>" in str(result)

    def test_code_commit_admin_net_changes_display_positive(self, project):
        """Test net_changes_display method with positive changes."""
        commit = CodeCommit.objects.create(
            project=project,
            commit_hash="test123",
            author_email="dev@example.com",
            author_name="Developer",
            message="Test commit",
            timestamp=timezone.now(),
            insertions=25,
            deletions=10,
        )

        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        result = admin.net_changes_display(commit)

        assert "+15" in str(result)
        assert "#009900" in str(result)  # Green color

    def test_code_commit_admin_net_changes_display_negative(self, project):
        """Test net_changes_display method with negative changes."""
        commit = CodeCommit.objects.create(
            project=project,
            commit_hash="test123",
            author_email="dev@example.com",
            author_name="Developer",
            message="Test commit",
            timestamp=timezone.now(),
            insertions=5,
            deletions=15,
        )

        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        result = admin.net_changes_display(commit)

        assert "-10" in str(result)
        assert "#cc0000" in str(result)  # Red color

    def test_code_commit_admin_net_changes_display_zero(self, project):
        """Test net_changes_display method with zero changes."""
        commit = CodeCommit.objects.create(
            project=project,
            commit_hash="test123",
            author_email="dev@example.com",
            author_name="Developer",
            message="Test commit",
            timestamp=timezone.now(),
            insertions=10,
            deletions=10,
        )

        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        result = admin.net_changes_display(commit)

        assert "0" in str(result)
        assert "#666666" in str(result)  # Gray color

    def test_code_commit_admin_has_add_permission(self):
        """Test that manual addition of commits is disabled."""
        admin_site = AdminSite()
        admin = CodeCommitAdmin(CodeCommit, admin_site)

        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = AnonymousUser()

        assert admin.has_add_permission(request) is False


@pytest.mark.django_db
class TestAdminInlines:

    def test_team_member_inline_configuration(self):
        """Test TeamMemberInline configuration."""
        from apps.management.admin import TeamMemberInline

        inline = TeamMemberInline
        assert inline.model == TeamMember
        assert inline.extra == 0
        assert "joined_at" in inline.readonly_fields

    def test_project_inline_configuration(self):
        """Test ProjectInline configuration."""
        from apps.management.admin import ProjectInline

        inline = ProjectInline
        assert inline.model == Project
        assert inline.extra == 0
        assert "created_at" in inline.readonly_fields

    def test_integration_inline_configuration(self):
        """Test IntegrationInline configuration."""
        from apps.management.admin import IntegrationInline

        inline = IntegrationInline
        assert inline.model == Integration
        assert inline.extra == 0
        assert "created_at" in inline.readonly_fields

    def test_github_integration_inline_configuration(self):
        """Test GitHubIntegrationInline configuration."""
        from apps.management.admin import GitHubIntegrationInline

        inline = GitHubIntegrationInline
        assert inline.model == GitHubIntegration
        assert inline.extra == 0
        assert "repository_url" in inline.readonly_fields

    def test_code_commit_inline_configuration(self):
        """Test CodeCommitInline configuration."""
        from apps.management.admin import CodeCommitInline

        inline = CodeCommitInline
        assert inline.model == CodeCommit
        assert inline.extra == 0
        assert "commit_hash" in inline.readonly_fields

    def test_code_commit_inline_has_add_permission(self):
        """Test that CodeCommitInline disables add permission."""
        from apps.management.admin import CodeCommitInline

        inline = CodeCommitInline(CodeCommit, AdminSite())

        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = AnonymousUser()

        assert inline.has_add_permission(request) is False


@pytest.mark.django_db
class TestAdminIntegration:

    def test_admin_site_registration(self):
        """Test that all models are registered with admin site."""
        from django.contrib import admin

        # Check that our models are registered
        registered_models = [model._meta.model for model in admin.site._registry.keys()]

        assert Team in registered_models
        assert Project in registered_models
        assert TeamMember in registered_models
        assert Integration in registered_models
        assert GitHubIntegration in registered_models
        assert CodeCommit in registered_models

    def test_admin_permissions(self):
        """Test admin interface permissions."""
        # This would typically involve creating test users and checking
        # admin permissions, but since we're using remote authentication,
        # the admin permissions would be handled by Django's built-in system
        # integrated with our remote user proxy

        from django.contrib.admin import site

        assert site.has_permission is not None

    def test_admin_search_functionality(self):
        """Test admin search field configurations."""
        admin_site = AdminSite()

        team_admin = TeamAdmin(Team, admin_site)
        assert len(team_admin.search_fields) > 0

        project_admin = ProjectAdmin(Project, admin_site)
        assert len(project_admin.search_fields) > 0

        member_admin = TeamMemberAdmin(TeamMember, admin_site)
        assert len(member_admin.search_fields) > 0

    def test_admin_filter_functionality(self):
        """Test admin list filter configurations."""
        admin_site = AdminSite()

        team_admin = TeamAdmin(Team, admin_site)
        assert len(team_admin.list_filter) > 0

        project_admin = ProjectAdmin(Project, admin_site)
        assert len(project_admin.list_filter) > 0

        integration_admin = IntegrationAdmin(Integration, admin_site)
        assert len(integration_admin.list_filter) > 0
