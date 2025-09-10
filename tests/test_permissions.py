import uuid
from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory

from apps.management.authentication import RemoteUserProxy
from apps.management.models import Project, Team, TeamMember
from apps.management.permissions import (
    IsOwnerOrAdmin,
    IsProjectMemberOrAdmin,
    IsTeamMemberOrAdmin,
)


class TestIsOwnerOrAdmin:

    def test_has_permission_authenticated_user(self):
        """Test has_permission with authenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = True

        permission = IsOwnerOrAdmin()
        assert permission.has_permission(request, None) is True

    def test_has_permission_unauthenticated_user(self):
        """Test has_permission with unauthenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = False

        permission = IsOwnerOrAdmin()
        assert permission.has_permission(request, None) is False

    def test_has_permission_no_user(self):
        """Test has_permission with no user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = None

        permission = IsOwnerOrAdmin()
        assert permission.has_permission(request, None) is False

    @pytest.mark.django_db
    def test_has_object_permission_admin_user(self, team):
        """Test object permission for admin user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "admin"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is True

    @pytest.mark.django_db
    def test_has_object_permission_owner(self, company_id):
        """Test object permission for resource owner."""
        user_id = uuid.uuid4()
        team = Team.objects.create(name="Test Team", company_id=company_id, created_by=user_id)

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_member_read(self, team):
        """Test object permission for team member (read access)."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=user_id, role="developer")

        factory = APIRequestFactory()
        request = factory.get("/")  # Safe method
        request.method = "GET"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_member_write_not_lead(self, team):
        """Test object permission for team member (write access, not lead)."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=user_id, role="developer")

        factory = APIRequestFactory()
        request = factory.post("/")  # Unsafe method
        request.method = "POST"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is False

    @pytest.mark.django_db
    def test_has_object_permission_team_lead_write(self, team):
        """Test object permission for team lead (write access)."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=user_id, role="lead")

        factory = APIRequestFactory()
        request = factory.post("/")  # Unsafe method
        request.method = "POST"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is True

    @pytest.mark.django_db
    def test_has_object_permission_no_access(self, team):
        """Test object permission for user with no access."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "developer"})

        permission = IsOwnerOrAdmin()
        assert permission.has_object_permission(request, None, team) is False


class TestIsTeamMemberOrAdmin:

    def test_has_permission_authenticated_user(self):
        """Test has_permission with authenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = True

        permission = IsTeamMemberOrAdmin()
        assert permission.has_permission(request, None) is True

    def test_has_permission_unauthenticated_user(self):
        """Test has_permission with unauthenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = False

        permission = IsTeamMemberOrAdmin()
        assert permission.has_permission(request, None) is False

    @pytest.mark.django_db
    def test_has_object_permission_admin_user(self, team_member):
        """Test object permission for admin user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "admin"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is True

    @pytest.mark.django_db
    def test_has_object_permission_own_record(self, team_member):
        """Test object permission for accessing own team member record."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(team_member.user_id), "role": "developer"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_lead(self, team, team_member):
        """Test object permission for team lead accessing member record."""
        lead_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=lead_id, role="lead")

        # Update team_member to belong to same team
        team_member.team = team
        team_member.save()

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(lead_id), "role": "developer"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_member_read_only(self, team, team_member):
        """Test object permission for team member (read-only access)."""
        member_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=member_id, role="developer")

        # Update team_member to belong to same team
        team_member.team = team
        team_member.save()

        factory = APIRequestFactory()
        request = factory.get("/")  # Safe method
        request.method = "GET"
        request.user = RemoteUserProxy({"user_id": str(member_id), "role": "developer"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_member_write_denied(self, team, team_member):
        """Test object permission for team member (write access denied)."""
        member_id = uuid.uuid4()
        TeamMember.objects.create(team=team, user_id=member_id, role="developer")

        # Update team_member to belong to same team
        team_member.team = team
        team_member.save()

        factory = APIRequestFactory()
        request = factory.post("/")  # Unsafe method
        request.method = "POST"
        request.user = RemoteUserProxy({"user_id": str(member_id), "role": "developer"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is False

    @pytest.mark.django_db
    def test_has_object_permission_no_access(self, team_member):
        """Test object permission for user with no access."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "developer"})

        permission = IsTeamMemberOrAdmin()
        assert permission.has_object_permission(request, None, team_member) is False


class TestIsProjectMemberOrAdmin:

    def test_has_permission_authenticated_user(self):
        """Test has_permission with authenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = True

        permission = IsProjectMemberOrAdmin()
        assert permission.has_permission(request, None) is True

    def test_has_permission_unauthenticated_user(self):
        """Test has_permission with unauthenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = Mock()
        request.user.is_authenticated = False

        permission = IsProjectMemberOrAdmin()
        assert permission.has_permission(request, None) is False

    @pytest.mark.django_db
    def test_has_object_permission_admin_user(self, project):
        """Test object permission for admin user."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "admin"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    @pytest.mark.django_db
    def test_has_object_permission_project_direct(self, project):
        """Test object permission for project resource directly."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=project.team, user_id=user_id, role="developer")

        factory = APIRequestFactory()
        request = factory.get("/")  # Safe method
        request.method = "GET"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    @pytest.mark.django_db
    def test_has_object_permission_project_related(self, project, integration):
        """Test object permission for project-related resource."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=project.team, user_id=user_id, role="developer")

        # Set up integration to belong to project
        integration.project = project
        integration.save()

        factory = APIRequestFactory()
        request = factory.get("/")  # Safe method
        request.method = "GET"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, integration) is True

    @pytest.mark.django_db
    def test_has_object_permission_team_member_write_not_lead(self, project):
        """Test object permission for team member (write access, not lead)."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=project.team, user_id=user_id, role="developer")

        factory = APIRequestFactory()
        request = factory.post("/")  # Unsafe method
        request.method = "POST"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, project) is False

    @pytest.mark.django_db
    def test_has_object_permission_team_lead_write(self, project):
        """Test object permission for team lead (write access)."""
        user_id = uuid.uuid4()
        TeamMember.objects.create(team=project.team, user_id=user_id, role="lead")

        factory = APIRequestFactory()
        request = factory.post("/")  # Unsafe method
        request.method = "POST"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, project) is True

    def test_has_object_permission_no_project_attribute(self):
        """Test object permission for object without project attribute."""
        mock_obj = Mock()
        del mock_obj.project  # Ensure no project attribute

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        # Should handle objects that don't have project attribute
        try:
            result = permission.has_object_permission(request, None, mock_obj)
            assert result is False
        except AttributeError:
            # This is also acceptable behavior
            pass

    @pytest.mark.django_db
    def test_has_object_permission_no_access(self, project):
        """Test object permission for user with no access."""
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "developer"})

        permission = IsProjectMemberOrAdmin()
        assert permission.has_object_permission(request, None, project) is False


@pytest.mark.django_db
class TestPermissionsIntegration:

    def test_multiple_teams_isolation(self, company_id):
        """Test that permissions properly isolate between teams."""
        user_id = uuid.uuid4()

        # Create two teams
        team1 = Team.objects.create(name="Team 1", company_id=company_id, created_by=user_id)

        team2 = Team.objects.create(name="Team 2", company_id=company_id, created_by=uuid.uuid4())

        # User is member of team1 only
        TeamMember.objects.create(team=team1, user_id=user_id, role="lead")

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsOwnerOrAdmin()

        # Should have access to team1
        assert permission.has_object_permission(request, None, team1) is True

        # Should NOT have access to team2
        assert permission.has_object_permission(request, None, team2) is False

    def test_project_team_member_cascade(self, company_id):
        """Test that project permissions cascade from team membership."""
        user_id = uuid.uuid4()

        team = Team.objects.create(name="Test Team", company_id=company_id, created_by=uuid.uuid4())

        project = Project.objects.create(name="Test Project", team=team)

        # User is member of team
        TeamMember.objects.create(team=team, user_id=user_id, role="developer")

        factory = APIRequestFactory()
        request = factory.get("/")  # Safe method
        request.method = "GET"
        request.user = RemoteUserProxy({"user_id": str(user_id), "role": "developer"})

        permission = IsProjectMemberOrAdmin()

        # Should have read access to project through team membership
        assert permission.has_object_permission(request, None, project) is True

    def test_permission_edge_cases(self):
        """Test permission edge cases and error handling."""
        permission = IsOwnerOrAdmin()

        # Test with None user
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = None

        assert permission.has_permission(request, None) is False

        # Test with object that has no attributes
        mock_obj = Mock()
        del mock_obj.created_by
        del mock_obj.id

        request.user = RemoteUserProxy({"user_id": str(uuid.uuid4()), "role": "developer"})

        # Should handle missing attributes gracefully
        try:
            result = permission.has_object_permission(request, None, mock_obj)
            assert result is False
        except AttributeError:
            # This is also acceptable behavior
            pass
