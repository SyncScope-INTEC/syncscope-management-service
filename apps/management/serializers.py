from rest_framework import serializers

from config.database_retry import database_retry

from .authentication import AuthServiceIntegration
from .models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
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

    def validate(self, attrs):
        """Validate team data."""
        # Set created_by from authenticated user
        if not attrs.get("created_by") and self.context.get("request"):
            user = self.context["request"].user
            if hasattr(user, "id"):
                attrs["created_by"] = user.id

        # Set company_id from authenticated user if not provided
        if not attrs.get("company_id") and self.context.get("request"):
            user = self.context["request"].user
            if hasattr(user, "company_id") and user.company_id:
                attrs["company_id"] = user.company_id

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
                is_member = TeamMember.objects.filter(
                    team=value, user_id=user.id
                ).exists()
                if not is_member:
                    raise serializers.ValidationError(
                        "You don't have permission to create projects for this team."
                    )
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

        # Check if user is already a member of the team
        if TeamMember.objects.filter(team=team, user_id=user_id).exists():
            raise serializers.ValidationError("User is already a member of this team.")

        # Validate that the requesting user has permission to add members
        if self.context.get("request"):
            requesting_user = self.context["request"].user
            if hasattr(requesting_user, "role") and requesting_user.role != "admin":
                # Check if requesting user is a team lead
                requesting_member = TeamMember.objects.filter(
                    team=team, user_id=requesting_user.id, role="lead"
                ).first()
                if not requesting_member:
                    raise serializers.ValidationError(
                        "You don't have permission to add members to this team."
                    )

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
                    raise serializers.ValidationError(
                        f"GitHub integration requires '{field}' in config_data."
                    )

        elif integration_type == "slack":
            required_fields = ["webhook_url"]
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(
                        f"Slack integration requires '{field}' in config_data."
                    )

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
            raise serializers.ValidationError(
                "This repository is already integrated with the project."
            )

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
    description = serializers.CharField(
        required=False, allow_blank=True, help_text="Team description"
    )


class TeamUpdateSerializer(serializers.Serializer):
    """Serializer for team update requests."""

    name = serializers.CharField(max_length=255, required=False, help_text="Team name")
    description = serializers.CharField(
        required=False, allow_blank=True, help_text="Team description"
    )


class ProjectCreateSerializer(serializers.Serializer):
    """Serializer for project creation requests."""

    name = serializers.CharField(max_length=255, help_text="Project name")
    description = serializers.CharField(
        required=False, allow_blank=True, help_text="Project description"
    )
    team_id = serializers.UUIDField(help_text="Team ID")
    repository_url = serializers.URLField(
        required=False, allow_blank=True, help_text="Repository URL"
    )
    url = serializers.URLField(
        required=False, allow_blank=True, help_text="Project URL"
    )


class TeamMemberCreateSerializer(serializers.Serializer):
    """Serializer for adding team members."""

    user_id = serializers.UUIDField(help_text="User ID to add to the team")
    role = serializers.ChoiceField(
        choices=TeamMember.ROLE_CHOICES,
        default="developer",
        help_text="Role in the team",
    )


class IntegrationCreateSerializer(serializers.Serializer):
    """Serializer for creating integrations."""

    project_id = serializers.UUIDField(help_text="Project ID")
    type = serializers.ChoiceField(
        choices=Integration.INTEGRATION_TYPE_CHOICES, help_text="Integration type"
    )
    config_data = serializers.JSONField(help_text="Integration configuration data")


class ErrorResponseSerializer(serializers.Serializer):
    """Generic error response serializer."""

    error = serializers.CharField()
    details = serializers.DictField(required=False)
