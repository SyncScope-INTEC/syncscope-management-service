"""
Django Admin configuration for Management models.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CodeCommit,
    GitHubIntegration,
    Integration,
    OrganizationSettings,
    Project,
    ProjectMember,
    Team,
    TeamMember,
)


class OrganizationSettingsForm(forms.ModelForm):
    """Custom form for OrganizationSettings admin."""

    # Add a custom password field for setting new passwords
    new_deletion_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Enter a new deletion password (min 8 chars, 1 uppercase, 1 number, 1 special character). "
        "Leave blank to keep current password or use default (company name lowercase).",
        label="New Deletion Password",
    )

    class Meta:
        model = OrganizationSettings
        fields = "__all__"

    def clean_new_deletion_password(self):
        """Validate the new deletion password if provided."""
        new_password = self.cleaned_data.get("new_deletion_password")

        if new_password:
            # Validate password complexity
            import re

            if len(new_password) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long.")

            if not re.search(r"[A-Z]", new_password):
                raise forms.ValidationError("Password must contain at least one uppercase letter.")

            if not re.search(r"\d", new_password):
                raise forms.ValidationError("Password must contain at least one number.")

            if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
                raise forms.ValidationError("Password must contain at least one special character.")

        return new_password

    def clean(self):
        """Validate the entire form."""
        cleaned_data = super().clean()

        # Ensure company_name is provided
        company_name = cleaned_data.get("company_name")
        if not company_name:
            raise forms.ValidationError({"company_name": "Company name is required."})

        # Ensure updated_by is provided
        if not cleaned_data.get("updated_by"):
            # Set it from request if available
            if hasattr(self, "_request"):
                cleaned_data["updated_by"] = self._request.user.id
            else:
                raise forms.ValidationError({"updated_by": "Updated by field is required."})

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # If a new password is provided, set it (already validated in clean_new_deletion_password)
        new_password = self.cleaned_data.get("new_deletion_password")
        if new_password:
            instance.set_deletion_password(new_password, validate_complexity=True)

        if commit:
            instance.save()
        return instance


# Monkey patch LogEntry to avoid UUID/integer conflicts
def safe_log_action(self, user_id, content_type_id, object_id, object_repr, action_flag, change_message=""):
    """
    Safe logging that doesn't create entries to avoid UUID/integer type conflicts.
    This is a temporary fix until the database schema is properly synchronized.
    """
    # Skip logging to avoid UUID/integer type mismatch errors
    pass


# Monkey patch AdminSite index to avoid LogEntry queries
def safe_index(self, request, extra_context=None):
    """
    Safe admin index that doesn't query recent actions to avoid UUID/integer conflicts.
    """
    from django.contrib.admin.sites import AdminSite
    from django.shortcuts import render

    # Get the original index context without recent actions
    app_list = safe_get_app_list(self, request)
    context = {
        **self.each_context(request),
        "title": self.index_title,
        "subtitle": None,
        "app_list": app_list,
        "username": request.user.get_username() if hasattr(request, "user") else None,
        **(extra_context or {}),
    }

    return render(request, self.index_template or "admin/index.html", context)


def safe_get_app_list(self, request):
    """
    Safe get_app_list that doesn't include recent actions to avoid LogEntry queries.
    """
    app_dict = {}

    for model, model_admin in self._registry.items():
        app_label = model._meta.app_label

        has_module_perms = model_admin.has_module_permission(request)
        if not has_module_perms:
            continue

        perms = model_admin.get_model_perms(request)
        if True not in perms.values():
            continue

        info = (app_label, model._meta.model_name)
        model_dict = {
            "name": str(model._meta.verbose_name_plural),
            "object_name": model._meta.object_name,
            "perms": perms,
            "admin_url": None,
            "add_url": None,
        }
        if perms.get("change") or perms.get("view"):
            model_dict["view_only"] = not perms.get("change")
            try:
                from django.urls import reverse

                model_dict["admin_url"] = reverse("admin:%s_%s_changelist" % info)
            except:
                pass
        if perms.get("add"):
            try:
                from django.urls import reverse

                model_dict["add_url"] = reverse("admin:%s_%s_add" % info)
            except:
                pass

        if app_label in app_dict:
            app_dict[app_label]["models"].append(model_dict)
        else:
            from django.urls import reverse

            try:
                app_url = reverse("admin:app_list", kwargs={"app_label": app_label})
            except:
                app_url = "#"

            app_dict[app_label] = {
                "name": app_label.title(),
                "app_label": app_label,
                "app_url": app_url,
                "has_module_perms": has_module_perms,
                "models": [model_dict],
            }

    app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())
    return app_list


# Apply the monkey patches
admin.ModelAdmin.log_action = safe_log_action
admin.site.index = safe_index.__get__(admin.site, admin.AdminSite)
admin.site.get_app_list = safe_get_app_list.__get__(admin.site, admin.AdminSite)


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Organization Settings."""

    list_display = (
        "company_name",
        "company_id",
        "protection_status",
        "failed_attempts_display",
        "password_updated_display",
        "updated_at",
    )
    list_filter = ("deletion_protection_enabled", "created_at", "updated_at")
    search_fields = ("company_name", "company_id", "last_failed_attempt_user")
    readonly_fields = (
        "id",
        "deletion_password_hash",
        "deletion_password_updated_at",
        "failed_deletion_attempts",
        "last_failed_attempt_at",
        "last_failed_attempt_user",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Organization Information",
            {"fields": ("company_id", "company_name", "updated_by")},
        ),
        (
            "Deletion Protection",
            {
                "fields": (
                    "deletion_protection_enabled",
                    "deletion_password_updated_at",
                ),
                "description": "Enable deletion protection to prevent unauthorized agent uninstallation. "
                "If no custom password is set, the company name (lowercase) will be used as the default password.",
            },
        ),
        (
            "Security Information",
            {
                "fields": (
                    "deletion_password_hash",
                    "failed_deletion_attempts",
                    "last_failed_attempt_at",
                    "last_failed_attempt_user",
                ),
                "classes": ("collapse",),
                "description": "View failed deletion attempts and security information. "
                "Failed attempts trigger email alerts to organization administrators.",
            },
        ),
        (
            "Metadata",
            {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def protection_status(self, obj):
        """Display deletion protection status with visual indicator."""
        if obj.deletion_protection_enabled:
            return format_html('<span style="color: #009900; font-weight: bold;">✓ Enabled</span>')
        return format_html('<span style="color: #cc0000;">✗ Disabled</span>')

    protection_status.short_description = "Protection Status"

    def failed_attempts_display(self, obj):
        """Display failed attempts count with warning color."""
        count = obj.failed_deletion_attempts
        if count > 0:
            if count >= 10:
                color = "#cc0000"  # Red for many failures
            elif count >= 5:
                color = "#ff9900"  # Orange for moderate failures
            else:
                color = "#666666"  # Gray for few failures
            return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, count)
        return format_html('<span style="color: #009900;">0</span>')

    failed_attempts_display.short_description = "Failed Attempts"

    def password_updated_display(self, obj):
        """Display when password was last updated."""
        if obj.deletion_password_updated_at:
            return obj.deletion_password_updated_at.strftime("%Y-%m-%d %H:%M")
        return format_html('<span style="color: #999999;">Never</span>')

    password_updated_display.short_description = "Password Updated"

    def get_form(self, request, obj=None, **kwargs):
        """Customize the admin form."""
        # Store request on form for access in clean method
        form_class = type("OrganizationSettingsFormWithRequest", (OrganizationSettingsForm,), {"_request": request})
        kwargs["form"] = form_class
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """Save the model and set updated_by to current user."""
        obj.updated_by = request.user.id
        super().save_model(request, obj, form, change)


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


class ProjectMemberInline(admin.TabularInline):
    """Inline admin for project members."""

    model = ProjectMember
    extra = 1
    readonly_fields = ("joined_at", "created_at", "updated_at")
    fields = ("user_id", "role", "joined_at")
    verbose_name = "Project Member"
    verbose_name_plural = "Project Members"


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
    inlines = [IntegrationInline, GitHubIntegrationInline, CodeCommitInline, ProjectMemberInline]

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
            kwargs["widget"] = admin.widgets.AdminTextareaWidget(attrs={"rows": 10, "cols": 80})
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
