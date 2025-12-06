"""
URL Configuration for the Management Service.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CodeCommitViewSet,
    GitHubIntegrationViewSet,
    IntegrationViewSet,
    OrganizationSettingsViewSet,
    ProjectMemberViewSet,
    ProjectViewSet,
    TeamMemberViewSet,
    TeamViewSet,
    api_home,
    get_git_events_team,
    get_user_projects,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"organization/settings", OrganizationSettingsViewSet, basename="organizationsettings")
router.register(r"teams", TeamViewSet, basename="team")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"team-members", TeamMemberViewSet, basename="teammember")
router.register(r"project-members", ProjectMemberViewSet, basename="projectmember")
router.register(r"integrations", IntegrationViewSet, basename="integration")
router.register(r"github-integrations", GitHubIntegrationViewSet, basename="githubintegration")
router.register(r"commits", CodeCommitViewSet, basename="codecommit")

app_name = "management"

urlpatterns = [
    path("", api_home, name="api_home"),
    path("", include(router.urls)),
    # User projects endpoint
    path("users/<uuid:user_id>/projects/", get_user_projects, name="get_user_projects"),
    # Analytics integration endpoints
    path("git-events/team/", get_git_events_team, name="get_git_events_team"),
]
