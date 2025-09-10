"""
Django Admin configuration for Management models.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    Project,
    Team,
    TeamMember,
)


class TeamMemberInline(admin.TabularInline):
    """Inline admin for team members."""

    model = TeamMember
    extra = 0
    readonly_fields = ("joined_at", "created_at", "updated_at")
    fields = ("user_id", "role", "joined_at")


class ProjectInline(admin.TabularInline):
    """Inline admin for projects."""

    model = Project
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = ("name", "description", "repository_url", "url")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin interface for Team model."""

    list_display = (
        "name",
        "company_id",
        "created_by",
        "members_count",
        "projects_count",
        "created_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("name", "description", "company_id", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [TeamMemberInline, ProjectInline]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        ("Relationships", {"fields": ("company_id", "created_by")}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def members_count(self, obj):
        """Display number of team members."""
        count = obj.members.count()
        return format_html('<span style="color: #0066cc;">{}</span>', count)

    members_count.short_description = "Members"

    def projects_count(self, obj):
        """Display number of projects."""
        count = obj.projects.count()
        return format_html('<span style="color: #009900;">{}</span>', count)

    projects_count.short_description = "Projects"


class IntegrationInline(admin.TabularInline):
    """Inline admin for integrations."""

    model = Integration
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = ("type", "is_active", "created_at")


class GitHubIntegrationInline(admin.TabularInline):
    """Inline admin for GitHub integrations."""

    model = GitHubIntegration
    extra = 0
    readonly_fields = ("repository_url", "last_sync", "created_at", "updated_at")
    fields = ("repository_owner", "repository_name", "is_active", "last_sync")


class CodeCommitInline(admin.TabularInline):
    """Inline admin for code commits."""

    model = CodeCommit
    extra = 0
    readonly_fields = (
        "commit_hash",
        "author_name",
        "message",
        "timestamp",
        "created_at",
    )
    fields = ("commit_hash", "author_name", "message", "timestamp")

    def has_add_permission(self, request, obj=None):
        """Disable adding commits through admin."""
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin interface for Project model."""

    list_display = (
        "name",
        "team",
        "repository_url",
        "integrations_count",
        "commits_count",
        "created_at",
    )
    list_filter = ("team", "created_at", "updated_at")
    search_fields = ("name", "description", "repository_url", "url")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [IntegrationInline, GitHubIntegrationInline, CodeCommitInline]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "team")}),
        ("URLs", {"fields": ("repository_url", "url")}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def integrations_count(self, obj):
        """Display number of active integrations."""
        count = obj.integrations.filter(is_active=True).count()
        return format_html('<span style="color: #ff9900;">{}</span>', count)

    integrations_count.short_description = "Active Integrations"

    def commits_count(self, obj):
        """Display number of commits."""
        count = obj.commits.count()
        return format_html('<span style="color: #9900cc;">{}</span>', count)

    commits_count.short_description = "Commits"


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    """Admin interface for TeamMember model."""

    list_display = ("user_id", "team", "role", "joined_at", "created_at")
    list_filter = ("role", "team", "joined_at", "created_at")
    search_fields = ("user_id", "team__name", "role")
    readonly_fields = ("id", "joined_at", "created_at", "updated_at")

    fieldsets = (
        ("Membership Information", {"fields": ("team", "user_id", "role")}),
        (
            "Metadata",
            {
                "fields": ("id", "joined_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    """Admin interface for Integration model."""

    list_display = ("project", "type", "is_active", "created_at")
    list_filter = ("type", "is_active", "created_at", "updated_at")
    search_fields = ("project__name", "type")
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        ("Integration Information", {"fields": ("project", "type", "is_active")}),
        (
            "Configuration",
            {
                "fields": ("config_data",),
                "description": "JSON configuration data for this integration",
            },
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize form fields."""
        if db_field.name == "config_data":
            kwargs["widget"] = admin.widgets.AdminTextareaWidget(
                attrs={"rows": 10, "cols": 80}
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(GitHubIntegration)
class GitHubIntegrationAdmin(admin.ModelAdmin):
    """Admin interface for GitHubIntegration model."""

    list_display = (
        "project",
        "repository_display",
        "is_active",
        "last_sync",
        "created_at",
    )
    list_filter = ("is_active", "last_sync", "created_at", "updated_at")
    search_fields = ("project__name", "repository_owner", "repository_name")
    readonly_fields = ("id", "repository_url", "last_sync", "created_at", "updated_at")

    fieldsets = (
        (
            "GitHub Repository",
            {
                "fields": (
                    "project",
                    "repository_owner",
                    "repository_name",
                    "repository_url",
                )
            },
        ),
        (
            "Authentication",
            {
                "fields": ("access_token", "webhook_secret"),
                "description": "GitHub access credentials (tokens are encrypted)",
            },
        ),
        ("Status", {"fields": ("is_active", "last_sync")}),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def repository_display(self, obj):
        """Display repository name as a link."""
        return format_html(
            '<a href="{}" target="_blank">{}/{}</a>',
            obj.repository_url,
            obj.repository_owner,
            obj.repository_name,
        )

    repository_display.short_description = "Repository"


@admin.register(CodeCommit)
class CodeCommitAdmin(admin.ModelAdmin):
    """Admin interface for CodeCommit model."""

    list_display = (
        "short_hash",
        "project",
        "author_name",
        "branch",
        "net_changes_display",
        "timestamp",
    )
    list_filter = ("project", "branch", "timestamp", "created_at")
    search_fields = (
        "project__name",
        "commit_hash",
        "author_name",
        "author_email",
        "message",
    )
    readonly_fields = ("id", "net_changes", "created_at")

    fieldsets = (
        (
            "Commit Information",
            {"fields": ("project", "commit_hash", "message", "branch")},
        ),
        (
            "Author Information",
            {"fields": ("author_name", "author_email", "timestamp")},
        ),
        (
            "Statistics",
            {"fields": ("files_changed", "insertions", "deletions", "net_changes")},
        ),
        ("Metadata", {"fields": ("id", "created_at"), "classes": ("collapse",)}),
    )

    def short_hash(self, obj):
        """Display shortened commit hash."""
        return format_html("<code>{}</code>", obj.commit_hash[:8])

    short_hash.short_description = "Hash"

    def net_changes_display(self, obj):
        """Display net changes with color coding."""
        net = obj.net_changes
        if net > 0:
            color = "#009900"
            prefix = "+"
        elif net < 0:
            color = "#cc0000"
            prefix = ""
        else:
            color = "#666666"
            prefix = ""
        return format_html('<span style="color: {};">{}{}</span>', color, prefix, net)

    net_changes_display.short_description = "Net Changes"

    def has_add_permission(self, request):
        """Disable manual addition of commits."""
        return False
