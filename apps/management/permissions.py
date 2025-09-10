"""
Custom permission classes for the Management Service.
"""

from rest_framework import permissions

from .models import Project, TeamMember


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission that allows access to admins or resource owners.
    Used for Team operations.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return bool(request.user and hasattr(request.user, "is_authenticated") and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """Check if user can access this team."""
        user = request.user

        # Admins can access everything
        if hasattr(user, "role") and user.role == "admin":
            return True

        # Check if user is the creator of the team
        if hasattr(user, "id") and hasattr(obj, "created_by"):
            if user.id == obj.created_by:
                return True

        # Check if user is a member of the team (for read operations)
        if hasattr(user, "id") and hasattr(obj, "id"):
            is_member = TeamMember.objects.filter(team=obj, user_id=user.id).exists()
            if is_member:
                # Team members can read, but only leads can modify
                if request.method in permissions.SAFE_METHODS:
                    return True
                else:
                    # Check if user is a team lead for write operations
                    is_lead = TeamMember.objects.filter(team=obj, user_id=user.id, role="lead").exists()
                    return is_lead

        return False


class IsTeamMemberOrAdmin(permissions.BasePermission):
    """
    Permission that allows access to admins or team members.
    Used for TeamMember operations.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return bool(request.user and hasattr(request.user, "is_authenticated") and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """Check if user can access this team member record."""
        user = request.user

        # Admins can access everything
        if hasattr(user, "role") and user.role == "admin":
            return True

        # Check if user is accessing their own membership record
        if hasattr(user, "id") and hasattr(obj, "user_id"):
            if user.id == obj.user_id:
                return True

        # Check if user is a lead of the team
        if hasattr(user, "id") and hasattr(obj, "team"):
            is_lead = TeamMember.objects.filter(team=obj.team, user_id=user.id, role="lead").exists()
            if is_lead:
                return True

        # Check if user is a member of the same team (for read operations)
        if hasattr(user, "id") and hasattr(obj, "team"):
            is_member = TeamMember.objects.filter(team=obj.team, user_id=user.id).exists()
            if is_member and request.method in permissions.SAFE_METHODS:
                return True

        return False


class IsProjectMemberOrAdmin(permissions.BasePermission):
    """
    Permission that allows access to admins or project team members.
    Used for Project, Integration, and CodeCommit operations.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return bool(request.user and hasattr(request.user, "is_authenticated") and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """Check if user can access this project-related resource."""
        user = request.user

        # Admins can access everything
        if hasattr(user, "role") and user.role == "admin":
            return True

        # Get the project object
        if hasattr(obj, "project"):
            project = obj.project
        elif isinstance(obj, Project):
            project = obj
        else:
            return False

        # Check if user is a member of the project's team
        if hasattr(user, "id") and hasattr(project, "team"):
            is_member = TeamMember.objects.filter(team=project.team, user_id=user.id).exists()
            if is_member:
                # Team members can read, but only leads can modify
                if request.method in permissions.SAFE_METHODS:
                    return True
                else:
                    # Check if user is a team lead for write operations
                    is_lead = TeamMember.objects.filter(team=project.team, user_id=user.id, role="lead").exists()
                    return is_lead

        return False
