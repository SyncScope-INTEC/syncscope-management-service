"""
URL Configuration for the Management Service.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CodeCommitViewSet,
    GitHubIntegrationViewSet,
    IntegrationViewSet,
    ProjectViewSet,
    TeamMemberViewSet,
    TeamViewSet,
    api_home,
    get_git_events_team,
    get_user_commits_analytics,
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r"teams", TeamViewSet, basename="team")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"team-members", TeamMemberViewSet, basename="teammember")
router.register(r"integrations", IntegrationViewSet, basename="integration")
router.register(r"github-integrations", GitHubIntegrationViewSet, basename="githubintegration")
router.register(r"commits", CodeCommitViewSet, basename="codecommit")

app_name = "management"

urlpatterns = [
    path("", api_home, name="api_home"),
    path("", include(router.urls)),
    # Analytics integration endpoints
    path("git-events/team/", get_git_events_team, name="get_git_events_team"),
    path("user-commits/analytics/", get_user_commits_analytics, name="get_user_commits_analytics"),
]
