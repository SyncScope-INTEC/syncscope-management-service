import sys
import uuid

from django.db import models
from django.utils import timezone

from config.database_retry import atomic_with_retry

from .db_mixins import RetryableManager, RetryableModelMixin


def get_table_name(base_name):
    """Get table name with or without schema prefix based on test mode."""
    if "test" in sys.argv or "pytest" in sys.modules:
        # SQLite doesn't support schemas, use simple table names for tests
        return base_name
    else:
        # PostgreSQL with management schema
        return f"management.{base_name}"


class Team(RetryableModelMixin, models.Model):
    """
    Model representing development teams.
    Maps to the management.teams table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    company_id = models.UUIDField(help_text="Reference to auth.companies.id")
    created_by = models.UUIDField(help_text="Reference to auth.users.id")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("teams")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company_id"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class Project(RetryableModelMixin, models.Model):
    """
    Model representing development projects.
    Maps to the management.projects table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="projects", db_column="team_id")
    repository_url = models.URLField(max_length=500, null=True, blank=True)
    url = models.URLField(max_length=500, null=True, blank=True, help_text="Project URL (e.g., live site)")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("projects")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team"]),
            models.Index(fields=["name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.team.name}"

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class TeamMember(RetryableModelMixin, models.Model):
    """
    Model representing team memberships.
    Maps to the management.team_members table.
    """

    ROLE_CHOICES = [
        ("lead", "Team Lead"),
        ("developer", "Developer"),
        ("senior_developer", "Senior Developer"),
        ("junior_developer", "Junior Developer"),
        ("intern", "Intern"),
        ("designer", "Designer"),
        ("qa", "QA Engineer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members", db_column="team_id")
    user_id = models.UUIDField(help_text="Reference to auth.users.id")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="developer")
    joined_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("team_members")
        ordering = ["-joined_at"]
        unique_together = ["team", "user_id"]
        indexes = [
            models.Index(fields=["team"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"User {self.user_id} - {self.team.name} ({self.role})"

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class Integration(RetryableModelMixin, models.Model):
    """
    Model representing project integrations.
    Maps to the management.integrations table.
    """

    INTEGRATION_TYPE_CHOICES = [
        ("github", "GitHub"),
        ("gitlab", "GitLab"),
        ("jira", "Jira"),
        ("slack", "Slack"),
        ("discord", "Discord"),
        ("teams", "Microsoft Teams"),
        ("trello", "Trello"),
        ("asana", "Asana"),
        ("jenkins", "Jenkins"),
        ("circleci", "CircleCI"),
        ("custom", "Custom Integration"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="integrations",
        db_column="project_id",
    )
    type = models.CharField(max_length=50, choices=INTEGRATION_TYPE_CHOICES)
    config_data = models.JSONField(default=dict, help_text="Integration-specific configuration data")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("integrations")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.project.name} - {self.get_type_display()}"

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class GitHubIntegration(RetryableModelMixin, models.Model):
    """
    Model representing GitHub-specific integrations.
    Maps to the management.github_integrations table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="github_integrations",
        db_column="project_id",
    )
    repository_owner = models.CharField(max_length=255)
    repository_name = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255, help_text="Encrypted GitHub access token")
    webhook_secret = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("github_integrations")
        ordering = ["-created_at"]
        unique_together = ["project", "repository_owner", "repository_name"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["repository_owner", "repository_name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.repository_owner}/{self.repository_name} - {self.project.name}"

    @property
    def repository_url(self):
        return f"https://github.com/{self.repository_owner}/{self.repository_name}"

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class CodeCommit(RetryableModelMixin, models.Model):
    """
    Model representing code commits from integrated repositories.
    Maps to the management.code_commits table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="commits",
        db_column="project_id",
    )
    commit_hash = models.CharField(max_length=40)
    author_email = models.EmailField()
    author_name = models.CharField(max_length=255)
    message = models.TextField()
    branch = models.CharField(max_length=255, default="main")
    timestamp = models.DateTimeField()
    files_changed = models.IntegerField(default=0)
    insertions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    objects = RetryableManager()

    class Meta:
        db_table = get_table_name("code_commits")
        ordering = ["-timestamp"]
        unique_together = ["project", "commit_hash"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["commit_hash"]),
            models.Index(fields=["author_email"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.commit_hash[:8]} - {self.project.name}"

    @property
    def net_changes(self):
        """Calculate net line changes."""
        return self.insertions - self.deletions

    @atomic_with_retry()
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
