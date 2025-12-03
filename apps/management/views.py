"""
API Views for the Management Service.
"""

from django.db import transaction
from django.http import HttpResponse
from django.template import loader
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from config.database_retry import atomic_with_retry

from .authentication import AuthServiceIntegration
from .db_mixins import ServerlessViewMixin
from .models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
    ProjectMember,
    Team,
    TeamMember,
)
from .permissions import IsOwnerOrAdmin, IsProjectMemberOrAdmin, IsTeamMemberOrAdmin
from .serializers import (
    CodeCommitSerializer,
    ErrorResponseSerializer,
    GitHubIntegrationSerializer,
    IntegrationCreateSerializer,
    IntegrationSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMemberCreateSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    TeamCreateSerializer,
    TeamDetailSerializer,
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    TeamSerializer,
    TeamUpdateSerializer,
)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def api_home(request):
    """
    API Home page showing main navigation routes and service links.
    """
    # Define the main navigation routes
    main_routes = [
        {
            "title": "API Documentation",
            "description": "Interactive API documentation with live testing",
            "url": request.build_absolute_uri("/api/docs/"),
            "icon": "📖",
            "category": "documentation",
        },
        {
            "title": "ReDoc Documentation",
            "description": "Clean, three-panel OpenAPI documentation",
            "url": request.build_absolute_uri("/api/redoc/"),
            "icon": "📚",
            "category": "documentation",
        },
        {
            "title": "OpenAPI Schema",
            "description": "Raw OpenAPI specification in JSON format",
            "url": request.build_absolute_uri("/api/schema/"),
            "icon": "⚙️",
            "category": "documentation",
        },
        {
            "title": "Admin Interface",
            "description": "Django admin panel for team and project management",
            "url": request.build_absolute_uri("/admin/"),
            "icon": "🔧",
            "category": "admin",
        },
        {
            "title": "Health Check",
            "description": "Service health status and monitoring",
            "url": request.build_absolute_uri("/health/"),
            "icon": "❤️",
            "category": "monitoring",
        },
    ]

    # Quick stats about the service
    service_info = {
        "endpoints": 25,
        "auth_methods": ["JWT", "Service Token"],
        "features": ["Team Management", "Project Tracking", "GitHub Integration", "Member Roles", "Code Metrics"],
        "status": "Operational",
    }

    context = {
        "main_routes": main_routes,
        "service_info": service_info,
        "api_title": "SyncScope Management Service",
        "api_version": "1.0.0",
        "api_description": "Team and project management service for SyncScope platform",
        "base_url": request.build_absolute_uri("/"),
    }

    # Check if JSON format is explicitly requested
    if request.GET.get("format") == "json":
        return Response(context, status=status.HTTP_200_OK)

    # Try to render HTML template first, fallback to JSON
    try:
        template = loader.get_template("management/api_home.html")
        return HttpResponse(template.render(context, request))
    except Exception as e:
        # Fallback to JSON response if template doesn't exist
        return Response(context, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=["Teams"],
        summary="List teams",
        description="Get a list of teams for the authenticated user's company.",
    ),
    create=extend_schema(
        tags=["Teams"],
        summary="Create team",
        description="Create a new team.",
        request=TeamCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=["Teams"],
        summary="Get team details",
        description="Get detailed information about a specific team.",
    ),
    update=extend_schema(
        tags=["Teams"],
        summary="Update team",
        description="Update team information.",
        request=TeamUpdateSerializer,
    ),
    partial_update=extend_schema(
        tags=["Teams"],
        summary="Partially update team",
        description="Partially update team information.",
        request=TeamUpdateSerializer,
    ),
    destroy=extend_schema(
        tags=["Teams"],
        summary="Delete team",
        description="Delete a team and all its associated data.",
    ),
)
class TeamViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing teams."""

    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        """Filter teams by user's company."""
        user = self.request.user
        if hasattr(user, "role") and user.role == "admin":
            return Team.objects.all()

        if hasattr(user, "company_id") and user.company_id:
            return Team.objects.filter(company_id=user.company_id)

        return Team.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "retrieve":
            return TeamDetailSerializer
        elif self.action == "create":
            return TeamCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return TeamUpdateSerializer
        return TeamSerializer

    @atomic_with_retry()
    def perform_create(self, serializer):
        """Create team with user context."""
        user = self.request.user

        # Create Team instance
        team_data = {
            "name": serializer.validated_data["name"],
            "description": serializer.validated_data.get("description", ""),
            "company_id": user.company_id if hasattr(user, "company_id") else None,
            "created_by": user.id if hasattr(user, "id") else None,
        }

        team = Team.objects.create(**team_data)

        # Auto-add creator as team lead
        if hasattr(user, "id"):
            TeamMember.objects.create(team=team, user_id=user.id, role="lead")

    @extend_schema(
        tags=["Teams"],
        summary="Get team members",
        description="Get all members of a specific team.",
    )
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        """Manage team members."""
        team = self.get_object()

        if request.method == "GET":
            members = TeamMember.objects.filter(team=team)
            serializer = TeamMemberSerializer(members, many=True, context={"request": request})
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = TeamMemberCreateSerializer(data=request.data)
            if serializer.is_valid():
                # Check permissions
                if not self._user_can_manage_team(request.user, team):
                    return Response(
                        {"error": "You don't have permission to manage this team."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Create team member
                TeamMember.objects.create(
                    team=team,
                    user_id=serializer.validated_data["user_id"],
                    role=serializer.validated_data.get("role", "developer"),
                )

                return Response(
                    {"message": "Team member added successfully."},
                    status=status.HTTP_201_CREATED,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Teams"],
        summary="Get team projects",
        description="Get all projects belonging to a specific team.",
    )
    @action(detail=True, methods=["get"])
    def projects(self, request, pk=None):
        """Get team projects."""
        team = self.get_object()
        projects = Project.objects.filter(team=team)
        serializer = ProjectSerializer(projects, many=True, context={"request": request})
        return Response(serializer.data)

    def _user_can_manage_team(self, user, team):
        """Check if user can manage team."""
        if hasattr(user, "role") and user.role == "admin":
            return True

        if hasattr(user, "id"):
            return TeamMember.objects.filter(team=team, user_id=user.id, role__in=["lead", "admin"]).exists()

        return False


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"],
        summary="List projects",
        description="Get a list of projects the user has access to.",
    ),
    create=extend_schema(
        tags=["Projects"],
        summary="Create project",
        description="Create a new project.",
        request=ProjectCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=["Projects"],
        summary="Get project details",
        description="Get detailed information about a specific project.",
    ),
    update=extend_schema(
        tags=["Projects"],
        summary="Update project",
        description="Update project information.",
    ),
    partial_update=extend_schema(
        tags=["Projects"],
        summary="Partially update project",
        description="Partially update project information.",
    ),
    destroy=extend_schema(
        tags=["Projects"],
        summary="Delete project",
        description="Delete a project and all its associated data.",
    ),
)
class ProjectViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing projects."""

    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberOrAdmin]

    def get_queryset(self):
        """Filter projects by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return Project.objects.all()

        if hasattr(user, "id"):
            # Get projects from teams user is a member of
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            return Project.objects.filter(team__in=user_teams)

        return Project.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "retrieve":
            return ProjectDetailSerializer
        elif self.action == "create":
            return ProjectCreateSerializer
        return ProjectSerializer

    @atomic_with_retry()
    def perform_create(self, serializer):
        """Create project with validation."""
        team_id = serializer.validated_data["team_id"]

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            raise serializers.ValidationError("Invalid team ID.")

        # Check if user has permission to create projects for this team
        user = self.request.user
        if not self._user_can_manage_team(user, team):
            raise serializers.ValidationError("You don't have permission to create projects for this team.")

        Project.objects.create(
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            team=team,
            repository_url=serializer.validated_data.get("repository_url"),
            url=serializer.validated_data.get("url"),
        )

    @extend_schema(
        tags=["Projects"],
        summary="Get project integrations",
        description="Get all integrations for a specific project.",
    )
    @action(detail=True, methods=["get", "post"])
    def integrations(self, request, pk=None):
        """Manage project integrations."""
        project = self.get_object()

        if request.method == "GET":
            integrations = Integration.objects.filter(project=project)
            serializer = IntegrationSerializer(integrations, many=True, context={"request": request})
            return Response(serializer.data)

        elif request.method == "POST":
            # Add project_id to the data for validation
            data = request.data.copy()
            data["project_id"] = project.id
            serializer = IntegrationCreateSerializer(data=data)
            if serializer.is_valid():
                Integration.objects.create(
                    project=project,
                    type=serializer.validated_data["type"],
                    config_data=serializer.validated_data["config_data"],
                )

                return Response(
                    {"message": "Integration created successfully."},
                    status=status.HTTP_201_CREATED,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Projects"],
        summary="Get project commits",
        description="Get recent commits for a specific project.",
    )
    @action(detail=True, methods=["get"])
    def commits(self, request, pk=None):
        """Get project commits."""
        project = self.get_object()
        commits = CodeCommit.objects.filter(project=project)[:50]  # Limit to recent 50
        serializer = CodeCommitSerializer(commits, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Projects"],
        summary="Manage project members",
        description="Get or add members to a specific project.",
    )
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        """Manage project members."""
        project = self.get_object()

        if request.method == "GET":
            members = ProjectMember.objects.filter(project=project)
            serializer = ProjectMemberSerializer(members, many=True, context={"request": request})
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = ProjectMemberCreateSerializer(data=request.data)
            if serializer.is_valid():
                # Check permissions
                if not self._user_can_manage_project(request.user, project):
                    return Response(
                        {"error": "You don't have permission to manage this project."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Validate that user is a member of the project's team
                user_id = serializer.validated_data["user_id"]
                if not TeamMember.objects.filter(team=project.team, user_id=user_id).exists():
                    return Response(
                        {"error": f"User must be a member of team '{project.team.name}' to be added to this project."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create project member
                ProjectMember.objects.create(
                    project=project,
                    user_id=serializer.validated_data["user_id"],
                    role=serializer.validated_data.get("role", "contributor"),
                )

                return Response(
                    {"message": "Project member added successfully."},
                    status=status.HTTP_201_CREATED,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _user_can_manage_team(self, user, team):
        """Check if user can manage team."""
        if hasattr(user, "role") and user.role == "admin":
            return True

        if hasattr(user, "id"):
            return TeamMember.objects.filter(team=team, user_id=user.id, role__in=["lead"]).exists()

        return False

    def _user_can_manage_project(self, user, project):
        """Check if user can manage project."""
        if hasattr(user, "role") and user.role == "admin":
            return True

        if hasattr(user, "id"):
            # Check if user is a project owner or team lead
            is_project_owner = ProjectMember.objects.filter(project=project, user_id=user.id, role="owner").exists()
            is_team_lead = TeamMember.objects.filter(team=project.team, user_id=user.id, role="lead").exists()
            return is_project_owner or is_team_lead

        return False


@extend_schema_view(
    list=extend_schema(
        tags=["Team Members"],
        summary="List team members",
        description="Get a list of all team members the user has access to.",
    ),
    create=extend_schema(
        tags=["Team Members"],
        summary="Add team member",
        description="Add a new member to a team.",
        request=TeamMemberCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=["Team Members"],
        summary="Get team member details",
        description="Get detailed information about a specific team member.",
    ),
    update=extend_schema(
        tags=["Team Members"],
        summary="Update team member",
        description="Update team member role or information.",
    ),
    partial_update=extend_schema(
        tags=["Team Members"],
        summary="Partially update team member",
        description="Partially update team member role or information.",
    ),
    destroy=extend_schema(
        tags=["Team Members"],
        summary="Remove team member",
        description="Remove a member from a team.",
    ),
)
class TeamMemberViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing team members."""

    serializer_class = TeamMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeamMemberOrAdmin]

    def get_queryset(self):
        """Filter team members by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return TeamMember.objects.all()

        if hasattr(user, "id"):
            # Get members from teams user is a member of
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            return TeamMember.objects.filter(team__in=user_teams)

        return TeamMember.objects.none()


@extend_schema_view(
    list=extend_schema(
        tags=["Project Members"],
        summary="List project members",
        description="Get a list of all project members the user has access to.",
    ),
    create=extend_schema(
        tags=["Project Members"],
        summary="Add project member",
        description="Add a new member to a project.",
        request=ProjectMemberCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=["Project Members"],
        summary="Get project member details",
        description="Get detailed information about a specific project member.",
    ),
    update=extend_schema(
        tags=["Project Members"],
        summary="Update project member",
        description="Update project member role or information.",
    ),
    partial_update=extend_schema(
        tags=["Project Members"],
        summary="Partially update project member",
        description="Partially update project member role or information.",
    ),
    destroy=extend_schema(
        tags=["Project Members"],
        summary="Remove project member",
        description="Remove a member from a project.",
    ),
)
class ProjectMemberViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing project members."""

    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberOrAdmin]

    def get_queryset(self):
        """Filter project members by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return ProjectMember.objects.all()

        if hasattr(user, "id"):
            # Get members from projects user has access to
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            user_projects = Project.objects.filter(team__in=user_teams).values_list("id", flat=True)
            return ProjectMember.objects.filter(project__in=user_projects)

        return ProjectMember.objects.none()


@extend_schema_view(
    list=extend_schema(
        tags=["Integrations"],
        summary="List integrations",
        description="Get a list of all integrations the user has access to.",
    ),
    create=extend_schema(
        tags=["Integrations"],
        summary="Create integration",
        description="Create a new integration for a project.",
        request=IntegrationCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=["Integrations"],
        summary="Get integration details",
        description="Get detailed information about a specific integration.",
    ),
    update=extend_schema(
        tags=["Integrations"],
        summary="Update integration",
        description="Update integration configuration.",
    ),
    partial_update=extend_schema(
        tags=["Integrations"],
        summary="Partially update integration",
        description="Partially update integration configuration.",
    ),
    destroy=extend_schema(
        tags=["Integrations"],
        summary="Delete integration",
        description="Delete an integration.",
    ),
)
class IntegrationViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing integrations."""

    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberOrAdmin]

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == "create":
            return IntegrationCreateSerializer
        return self.serializer_class

    def get_queryset(self):
        """Filter integrations by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return Integration.objects.all()

        if hasattr(user, "id"):
            # Get integrations from projects user has access to
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            user_projects = Project.objects.filter(team__in=user_teams).values_list("id", flat=True)
            return Integration.objects.filter(project__in=user_projects)

        return Integration.objects.none()


@extend_schema_view(
    list=extend_schema(
        tags=["Integrations"],
        summary="List GitHub integrations",
        description="Get a list of all GitHub integrations the user has access to.",
    ),
    create=extend_schema(
        tags=["Integrations"],
        summary="Create GitHub integration",
        description="Create a new GitHub integration for a project.",
    ),
    retrieve=extend_schema(
        tags=["Integrations"],
        summary="Get GitHub integration details",
        description="Get detailed information about a specific GitHub integration.",
    ),
    update=extend_schema(
        tags=["Integrations"],
        summary="Update GitHub integration",
        description="Update GitHub integration configuration.",
    ),
    partial_update=extend_schema(
        tags=["Integrations"],
        summary="Partially update GitHub integration",
        description="Partially update GitHub integration configuration.",
    ),
    destroy=extend_schema(
        tags=["Integrations"],
        summary="Delete GitHub integration",
        description="Delete a GitHub integration.",
    ),
)
class GitHubIntegrationViewSet(ServerlessViewMixin, viewsets.ModelViewSet):
    """ViewSet for managing GitHub integrations."""

    serializer_class = GitHubIntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberOrAdmin]

    def get_queryset(self):
        """Filter GitHub integrations by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return GitHubIntegration.objects.all()

        if hasattr(user, "id"):
            # Get GitHub integrations from projects user has access to
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            user_projects = Project.objects.filter(team__in=user_teams).values_list("id", flat=True)
            return GitHubIntegration.objects.filter(project__in=user_projects)

        return GitHubIntegration.objects.none()

    @extend_schema(
        tags=["Integrations"],
        summary="Sync GitHub integration",
        description="Trigger a manual sync for a GitHub integration.",
    )
    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Trigger manual sync for GitHub integration."""
        integration = self.get_object()

        # TODO: Implement GitHub sync logic
        # This would fetch latest commits, pull requests, etc.

        integration.last_sync = timezone.now()
        integration.save()

        return Response(
            {"message": "GitHub sync triggered successfully."},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Projects"],
        summary="List code commits",
        description="Get a list of code commits the user has access to.",
    ),
    retrieve=extend_schema(
        tags=["Projects"],
        summary="Get commit details",
        description="Get detailed information about a specific commit.",
    ),
)
class CodeCommitViewSet(ServerlessViewMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for code commits."""

    serializer_class = CodeCommitSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMemberOrAdmin]

    def get_queryset(self):
        """Filter commits by user access."""
        user = self.request.user

        if hasattr(user, "role") and user.role == "admin":
            return CodeCommit.objects.all()

        if hasattr(user, "id"):
            # Get commits from projects user has access to
            user_teams = TeamMember.objects.filter(user_id=user.id).values_list("team", flat=True)
            user_projects = Project.objects.filter(team__in=user_teams).values_list("id", flat=True)
            return CodeCommit.objects.filter(project__in=user_projects)

        return CodeCommit.objects.none()


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
@extend_schema(
    tags=["Projects"],
    summary="Get user's projects",
    description="Get all projects for a specific user. User can access their own projects or admins can access any user's projects.",
)
def get_user_projects(request, user_id):
    """
    API endpoint to get all projects for a specific user.
    Projects are returned based on:
    1. Direct project membership (ProjectMember)
    2. Team membership (TeamMember -> Team -> Projects)
    """
    # Permission check
    requesting_user = request.user
    if not (hasattr(requesting_user, "role") and requesting_user.role == "admin"):
        if not (hasattr(requesting_user, "id") and str(requesting_user.id) == str(user_id)):
            return Response(
                {"error": "You don't have permission to view this user's projects."},
                status=status.HTTP_403_FORBIDDEN,
            )

    try:
        # Get projects where user is a direct member
        direct_projects = Project.objects.filter(members__user_id=user_id).distinct()

        # Get projects from teams user is a member of
        user_teams = TeamMember.objects.filter(user_id=user_id).values_list("team", flat=True)
        team_projects = Project.objects.filter(team__in=user_teams).distinct()

        # Combine both querysets and remove duplicates
        all_projects = (direct_projects | team_projects).distinct()

        serializer = ProjectDetailSerializer(all_projects, many=True, context={"request": request})
        return Response(
            {
                "user_id": user_id,
                "projects": serializer.data,
                "total_projects": all_projects.count(),
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to get user projects: {str(e)}", "user_id": user_id, "projects": [], "total_projects": 0},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def favicon_view(request):
    """
    Simple favicon handler that serves SVG as ICO.
    """
    from django.shortcuts import redirect
    from django.templatetags.static import static

    # Redirect to the static SVG file
    svg_url = static("management/images/syncscope-logo.svg")
    return redirect(svg_url)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def api_get_team_members(request, team_id):
    """
    API endpoint for analytics service integration to get team members.
    """
    try:
        # For the "default" team, return a default structure
        if team_id == "default":
            return Response(
                {
                    "team_id": "default",
                    "name": "Default Team",
                    "members": [
                        {
                            "user_id": "default-user",
                            "username": "default_user",
                            "role": "member",
                            "joined_at": "2024-01-01T00:00:00Z",
                        }
                    ],
                    "member_count": 1,
                }
            )

        # Try to get the actual team
        try:
            team = Team.objects.get(id=team_id)
            members = TeamMember.objects.filter(team=team)
            serializer = TeamMemberSerializer(members, many=True)

            return Response(
                {"team_id": str(team.id), "name": team.name, "members": serializer.data, "member_count": members.count()}
            )
        except Team.DoesNotExist:
            return Response(
                {"error": f"Team '{team_id}' not found", "team_id": team_id, "members": [], "member_count": 0}, status=404
            )

    except Exception as e:
        return Response(
            {"error": f"Failed to get team members: {str(e)}", "team_id": team_id, "members": [], "member_count": 0},
            status=500,
        )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def get_git_events_team(request):
    """
    API endpoint for analytics service integration to get git events for team.
    """
    try:
        # For now, return mock data since we don't have git events model yet
        # This should be connected to actual git events data in the future
        return Response(
            {
                "events": [
                    {
                        "event_id": "git-event-1",
                        "team_id": "default",
                        "repository": "syncscope-platform",
                        "event_type": "push",
                        "timestamp": "2024-01-01T10:00:00Z",
                        "author": "developer@example.com",
                        "commits": 2,
                        "additions": 150,
                        "deletions": 30,
                    }
                ],
                "total_events": 1,
                "period": {
                    "start_date": request.GET.get("start_date", "2024-01-01T00:00:00Z"),
                    "end_date": request.GET.get("end_date", "2024-12-31T23:59:59Z"),
                },
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to get git events: {str(e)}", "events": [], "total_events": 0},
            status=500,
        )
