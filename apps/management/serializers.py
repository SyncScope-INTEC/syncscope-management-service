from rest_framework import serializers

from config.database_retry import database_retry

from .authentication import AuthServiceIntegration
from .models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    OrganizationSettings,
    Project,
    ProjectInvitation,
    ProjectMember,
    Team,
    TeamMember,
)


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for Team model."""

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "description",
            "company_id",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "company_id": {"required": False},
            "created_by": {"required": False},
        }

    def validate(self, attrs):
        """Validate team data."""
        # Set created_by from authenticated user
        if not attrs.get("created_by") and self.context.get("request"):
            user = self.context["request"].user
            if hasattr(user, "id") and user.id:
                # Ensure it's a UUID, not a string
                import uuid

                if isinstance(user.id, str):
                    attrs["created_by"] = uuid.UUID(user.id)
                else:
                    attrs["created_by"] = user.id

        # Set company_id from authenticated user if not provided
        if not attrs.get("company_id") and self.context.get("request"):
            user = self.context["request"].user
            if hasattr(user, "company_id") and user.company_id:
                # Ensure it's a UUID, not a string
                import uuid

                if isinstance(user.company_id, str):
                    attrs["company_id"] = uuid.UUID(user.company_id)
                else:
                    attrs["company_id"] = user.company_id

        # For tests without context, provide default values
        if not self.context.get("request"):
            import uuid

            if not attrs.get("created_by"):
                attrs["created_by"] = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")  # Test user ID
            if not attrs.get("company_id"):
                attrs["company_id"] = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")  # Test company ID

        return attrs


class TeamDetailSerializer(TeamSerializer):
    """Detailed serializer for Team with related data."""

    members_count = serializers.SerializerMethodField()
    projects_count = serializers.SerializerMethodField()

    class Meta(TeamSerializer.Meta):
        fields = TeamSerializer.Meta.fields + ["members_count", "projects_count"]

    def get_members_count(self, obj):
        return obj.members.count()

    def get_projects_count(self, obj):
        return obj.projects.count()


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for Project model."""

    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "team",
            "team_name",
            "repository_url",
            "url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "team_name", "created_at", "updated_at"]

    def validate_team(self, value):
        """Validate that the user has access to the team."""
        if self.context.get("request"):
            user = self.context["request"].user
            # Check if user belongs to the team or is admin
            if hasattr(user, "role") and user.role == "admin":
                return value

            # Check if user is a member of the team
            if hasattr(user, "id"):
                is_member = TeamMember.objects.filter(team=value, user_id=user.id).exists()
                if not is_member:
                    raise serializers.ValidationError("You don't have permission to create projects for this team.")
        return value


class ProjectDetailSerializer(ProjectSerializer):
    """Detailed serializer for Project with related data."""

    integrations_count = serializers.SerializerMethodField()
    commits_count = serializers.SerializerMethodField()
    latest_commit = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + [
            "integrations_count",
            "commits_count",
            "latest_commit",
        ]

    def get_integrations_count(self, obj):
        return obj.integrations.filter(is_active=True).count()

    def get_commits_count(self, obj):
        return obj.commits.count()

    def get_latest_commit(self, obj):
        latest = obj.commits.first()
        if latest:
            return {
                "hash": latest.commit_hash[:8],
                "message": latest.message,
                "author": latest.author_name,
                "timestamp": latest.timestamp,
            }
        return None


class TeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for TeamMember model."""

    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = TeamMember
        fields = [
            "id",
            "team",
            "team_name",
            "user_id",
            "user_email",
            "user_name",
            "role",
            "joined_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "team_name",
            "user_email",
            "user_name",
            "created_at",
            "updated_at",
        ]

    def get_user_email(self, obj):
        """Get user email from auth service."""
        if self.context.get("request"):
            token = getattr(self.context["request"], "auth", None)
            user_data = AuthServiceIntegration.get_user_by_id(obj.user_id, token)
            return user_data.get("email") if user_data else "Unknown"
        return "Unknown"

    def get_user_name(self, obj):
        """Get user name from auth service."""
        if self.context.get("request"):
            token = getattr(self.context["request"], "auth", None)
            user_data = AuthServiceIntegration.get_user_by_id(obj.user_id, token)
            if user_data:
                first_name = user_data.get("first_name", "")
                last_name = user_data.get("last_name", "")
                return f"{first_name} {last_name}".strip()
        return "Unknown User"

    def validate(self, attrs):
        """Validate team member data."""
        team = attrs.get("team")
        user_id = attrs.get("user_id")

        # Only run these validations for creation, not updates
        if not self.instance:  # self.instance is None for creation, set for updates
            # Check if user is already a member of the team
            if team and user_id and TeamMember.objects.filter(team=team, user_id=user_id).exists():
                raise serializers.ValidationError("User is already a member of this team.")

            # Validate that the requesting user has permission to add members
            if self.context.get("request") and team:
                requesting_user = self.context["request"].user
                if hasattr(requesting_user, "role") and requesting_user.role != "admin":
                    # Check if requesting user is a team lead
                    requesting_member = TeamMember.objects.filter(team=team, user_id=requesting_user.id, role="lead").first()
                    if not requesting_member:
                        raise serializers.ValidationError("You don't have permission to add members to this team.")

        return attrs


class ProjectMemberSerializer(serializers.ModelSerializer):
    """Serializer for ProjectMember model."""

    user_email = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            "id",
            "project",
            "project_name",
            "user_id",
            "user_email",
            "user_name",
            "role",
            "joined_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "user_email",
            "user_name",
            "created_at",
            "updated_at",
        ]

    def get_user_email(self, obj):
        """Get user email from auth service."""
        if self.context.get("request"):
            token = getattr(self.context["request"], "auth", None)
            user_data = AuthServiceIntegration.get_user_by_id(obj.user_id, token)
            return user_data.get("email") if user_data else "Unknown"
        return "Unknown"

    def get_user_name(self, obj):
        """Get user name from auth service."""
        if self.context.get("request"):
            token = getattr(self.context["request"], "auth", None)
            user_data = AuthServiceIntegration.get_user_by_id(obj.user_id, token)
            if user_data:
                first_name = user_data.get("first_name", "")
                last_name = user_data.get("last_name", "")
                return f"{first_name} {last_name}".strip()
        return "Unknown User"

    def validate(self, attrs):
        """Validate project member data."""
        project = attrs.get("project")
        user_id = attrs.get("user_id")

        # Only run these validations for creation, not updates
        if not self.instance:
            # Check if user is already a member of the project
            if project and user_id and ProjectMember.objects.filter(project=project, user_id=user_id).exists():
                raise serializers.ValidationError("User is already a member of this project.")

            # Check if user is a member of the project's team (safeguard)
            if project and user_id:
                if not TeamMember.objects.filter(team=project.team, user_id=user_id).exists():
                    raise serializers.ValidationError(
                        f"User must be a member of team '{project.team.name}' to be added to this project."
                    )

            # Validate that the requesting user has permission to add members
            if self.context.get("request") and project:
                requesting_user = self.context["request"].user
                if hasattr(requesting_user, "role") and requesting_user.role != "admin":
                    # Check if requesting user is a project owner or team lead
                    is_project_owner = ProjectMember.objects.filter(
                        project=project, user_id=requesting_user.id, role="owner"
                    ).exists()
                    is_team_lead = TeamMember.objects.filter(
                        team=project.team, user_id=requesting_user.id, role="lead"
                    ).exists()

                    if not is_project_owner and not is_team_lead:
                        raise serializers.ValidationError("You don't have permission to add members to this project.")

        return attrs


class IntegrationSerializer(serializers.ModelSerializer):
    """Serializer for Integration model."""

    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Integration
        fields = [
            "id",
            "project",
            "project_name",
            "type",
            "config_data",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project_name", "created_at", "updated_at"]

    def validate_config_data(self, value):
        """Validate config data based on integration type."""
        integration_type = self.initial_data.get("type")

        if integration_type == "github":
            required_fields = ["repository_owner", "repository_name"]
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"GitHub integration requires '{field}' in config_data.")

        elif integration_type == "slack":
            required_fields = ["webhook_url"]
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"Slack integration requires '{field}' in config_data.")

        return value


class GitHubIntegrationSerializer(serializers.ModelSerializer):
    """Serializer for GitHub Integration model."""

    project_name = serializers.CharField(source="project.name", read_only=True)
    repository_url = serializers.CharField(read_only=True)

    class Meta:
        model = GitHubIntegration
        fields = [
            "id",
            "project",
            "project_name",
            "repository_owner",
            "repository_name",
            "repository_url",
            "is_active",
            "last_sync",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "repository_url",
            "last_sync",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate GitHub integration data."""
        project = attrs.get("project")
        repository_owner = attrs.get("repository_owner")
        repository_name = attrs.get("repository_name")

        # Check if this repository is already integrated with the project
        if GitHubIntegration.objects.filter(
            project=project,
            repository_owner=repository_owner,
            repository_name=repository_name,
        ).exists():
            raise serializers.ValidationError("This repository is already integrated with the project.")

        return attrs


class CodeCommitSerializer(serializers.ModelSerializer):
    """Serializer for Code Commit model."""

    project_name = serializers.CharField(source="project.name", read_only=True)
    net_changes = serializers.CharField(read_only=True)

    class Meta:
        model = CodeCommit
        fields = [
            "id",
            "project",
            "project_name",
            "commit_hash",
            "author_email",
            "author_name",
            "message",
            "branch",
            "timestamp",
            "files_changed",
            "insertions",
            "deletions",
            "net_changes",
            "created_at",
        ]
        read_only_fields = ["id", "project_name", "net_changes", "created_at"]


# Request/Response Serializers for API endpoints


class TeamCreateSerializer(serializers.Serializer):
    """Serializer for team creation requests."""

    name = serializers.CharField(max_length=255, help_text="Team name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Team description")


class TeamUpdateSerializer(serializers.Serializer):
    """Serializer for team update requests."""

    name = serializers.CharField(max_length=255, required=False, help_text="Team name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Team description")

    def update(self, instance, validated_data):
        """Update team instance with validated data."""
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class ProjectCreateSerializer(serializers.Serializer):
    """Serializer for project creation requests."""

    name = serializers.CharField(max_length=255, help_text="Project name")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Project description")
    team_id = serializers.UUIDField(help_text="Team ID")
    repository_url = serializers.URLField(required=False, allow_blank=True, help_text="Repository URL")
    url = serializers.URLField(required=False, allow_blank=True, help_text="Project URL")


class TeamMemberCreateSerializer(serializers.Serializer):
    """Serializer for adding team members."""

    user_id = serializers.UUIDField(help_text="User ID to add to the team")
    role = serializers.ChoiceField(
        choices=TeamMember.ROLE_CHOICES,
        default="developer",
        help_text="Role in the team",
    )


class ProjectMemberCreateSerializer(serializers.Serializer):
    """Serializer for adding project members."""

    user_id = serializers.UUIDField(help_text="User ID to add to the project")
    role = serializers.ChoiceField(
        choices=ProjectMember.ROLE_CHOICES,
        default="contributor",
        help_text="Role in the project",
    )


class IntegrationCreateSerializer(serializers.Serializer):
    """Serializer for creating integrations."""

    project_id = serializers.UUIDField(help_text="Project ID")
    type = serializers.ChoiceField(choices=Integration.INTEGRATION_TYPE_CHOICES, help_text="Integration type")
    config_data = serializers.JSONField(help_text="Integration configuration data")

    def create(self, validated_data):
        """Create integration instance from validated data."""
        project_id = validated_data.pop("project_id")
        project = Project.objects.get(id=project_id)
        return Integration.objects.create(project=project, **validated_data)

    def validate_config_data(self, value):
        """Validate config data based on integration type."""
        integration_type = self.initial_data.get("type")

        if integration_type == "github":
            required_fields = ["repository_owner", "repository_name"]
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"GitHub integration requires '{field}' in config_data.")

        elif integration_type == "slack":
            required_fields = ["webhook_url"]
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"Slack integration requires '{field}' in config_data.")

        return value


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for Organization Settings."""

    class Meta:
        model = OrganizationSettings
        fields = [
            "id",
            "company_id",
            "company_name",
            "deletion_protection_enabled",
            "deletion_password_hash",  # Include for authenticated users (agent needs this for offline mode)
            "deletion_password_updated_at",
            "failed_deletion_attempts",
            "last_failed_attempt_at",
            "last_failed_attempt_user",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "deletion_password_hash",  # Read-only, set via set_deletion_password() method
            "deletion_password_updated_at",
            "failed_deletion_attempts",
            "last_failed_attempt_at",
            "last_failed_attempt_user",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """
        Customize representation to conditionally include password hash.

        The password hash is only included for authenticated users so that
        the agent can cache it locally for offline deletion protection verification.
        """
        data = super().to_representation(instance)

        # Only include password hash for authenticated requests
        # For unauthenticated or non-existent requests, remove the hash
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            data.pop("deletion_password_hash", None)

        return data


class OrganizationSettingsUpdateSerializer(serializers.Serializer):
    """Serializer for updating organization settings."""

    deletion_protection_enabled = serializers.BooleanField(required=False, help_text="Enable/disable deletion protection")
    new_deletion_password = serializers.CharField(
        required=False,
        write_only=True,
        min_length=8,
        help_text="New deletion password (min 8 chars, 1 uppercase, 1 number, 1 special character)",
    )

    def validate(self, attrs):
        """Validate the update data."""
        new_password = attrs.get("new_deletion_password")

        # If a password is provided, validate it
        if new_password:
            import re

            # Check password complexity
            if len(new_password) < 8:
                raise serializers.ValidationError({"new_deletion_password": "Password must be at least 8 characters long."})

            if not re.search(r"[A-Z]", new_password):
                raise serializers.ValidationError(
                    {"new_deletion_password": "Password must contain at least one uppercase letter."}
                )

            if not re.search(r"\d", new_password):
                raise serializers.ValidationError({"new_deletion_password": "Password must contain at least one number."})

            if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
                raise serializers.ValidationError(
                    {"new_deletion_password": "Password must contain at least one special character."}
                )

        return attrs

    def update(self, instance, validated_data):
        """Update organization settings."""
        new_password = validated_data.pop("new_deletion_password", None)

        # Update regular fields
        for field, value in validated_data.items():
            setattr(instance, field, value)

        # Update password if provided
        if new_password:
            instance.set_deletion_password(new_password, validate_complexity=True)

        instance.save()
        return instance


class VerifyDeletionPasswordSerializer(serializers.Serializer):
    """Serializer for deletion password verification."""

    password = serializers.CharField(required=True, write_only=True, help_text="Deletion password to verify")
    user_identifier = serializers.CharField(
        required=False, write_only=True, help_text="Username or email of user attempting deletion (for tracking)"
    )


class VerifyDeletionPasswordResponseSerializer(serializers.Serializer):
    """Response serializer for password verification."""

    valid = serializers.BooleanField(help_text="Whether the password is valid")
    protection_enabled = serializers.BooleanField(help_text="Whether deletion protection is enabled")
    message = serializers.CharField(required=False, help_text="Additional message or info")


class ErrorResponseSerializer(serializers.Serializer):
    """Generic error response serializer."""

    error = serializers.CharField()
    details = serializers.DictField(required=False)


# ==================== Project Invitation Serializers ====================


class ProjectInvitationSerializer(serializers.ModelSerializer):
    """Serializer for listing project invitations."""

    project_name = serializers.CharField(source="project.name", read_only=True)
    team_name = serializers.CharField(source="project.team.name", read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = ProjectInvitation
        fields = [
            "id",
            "project",
            "project_name",
            "team_name",
            "inviter_id",
            "invitee_email",
            "role",
            "token",
            "created_at",
            "expires_at",
            "is_accepted",
            "accepted_at",
            "accepted_by_id",
            "auto_added_to_team",
            "is_expired",
        ]
        read_only_fields = [
            "id",
            "token",
            "created_at",
            "expires_at",
            "is_accepted",
            "accepted_at",
            "accepted_by_id",
            "auto_added_to_team",
        ]

    def get_is_expired(self, obj):
        """Check if invitation has expired."""
        from django.utils import timezone

        return obj.expires_at <= timezone.now()


class CreateProjectInvitationSerializer(serializers.Serializer):
    """Serializer for creating project invitations."""

    project_id = serializers.UUIDField(required=True)
    invitee_email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(
        choices=[("supervisor", "Supervisor"), ("developer", "Developer")], default="developer"
    )

    def validate_invitee_email(self, value):
        """Validate email format."""
        from django.core.validators import EmailValidator, ValidationError

        validator = EmailValidator()
        try:
            validator(value)
        except ValidationError:
            raise serializers.ValidationError("Invalid email address")
        return value.lower()

    def validate_project_id(self, value):
        """Validate project exists."""
        try:
            project = Project.objects.get(id=value)
            self.context["project"] = project
            return value
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project not found")

    def validate(self, data):
        """Cross-field validation."""
        from django.utils import timezone

        project = self.context.get("project")
        invitee_email = data["invitee_email"]

        # Check if user already has an active invitation
        active_invitation = ProjectInvitation.objects.filter(
            project=project, invitee_email=invitee_email, is_accepted=False, expires_at__gt=timezone.now()
        ).first()

        if active_invitation:
            raise serializers.ValidationError(f"An active invitation already exists for {invitee_email}")

        return data


class InviteProjectUserResponseSerializer(serializers.Serializer):
    """Response serializer for project invitation creation."""

    message = serializers.CharField()
    invitation_id = serializers.UUIDField()
    invitee_email = serializers.EmailField()
    project_name = serializers.CharField()


class AcceptProjectInvitationSerializer(serializers.Serializer):
    """Serializer for accepting project invitations."""

    token = serializers.CharField(required=True)

    def validate_token(self, value):
        """Validate invitation token."""
        invitation = ProjectInvitation.get_active_invitation(value)
        if not invitation:
            raise serializers.ValidationError("Invalid or expired invitation token")

        self.context["invitation"] = invitation
        return value


class AcceptProjectInvitationResponseSerializer(serializers.Serializer):
    """Response serializer for accepting project invitation."""

    message = serializers.CharField()
    project_name = serializers.CharField()
    team_name = serializers.CharField()
    role = serializers.CharField()
    auto_added_to_team = serializers.BooleanField()
