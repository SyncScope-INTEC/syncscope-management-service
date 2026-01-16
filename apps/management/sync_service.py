"""
Sync service for synchronizing code commits from multiple sources.

This module provides functions to sync commits from:
1. Monitoring service (git events recorded by the developer agent)
2. GitHub API (commits fetched directly from GitHub repositories)
"""

import logging
from datetime import datetime
from typing import Optional

import requests
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from .models import CodeCommit, GitHubIntegration, Project

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""

    def __init__(self):
        self.commits_created = 0
        self.commits_skipped = 0
        self.errors = []

    def __str__(self):
        return f"Created: {self.commits_created}, Skipped: {self.commits_skipped}, Errors: {len(self.errors)}"


def sync_from_monitoring_service(
    integration: GitHubIntegration,
    since: Optional[datetime] = None,
    full_sync: bool = False,
) -> SyncResult:
    """
    Sync commits from the monitoring service's git_events table.

    Args:
        integration: GitHubIntegration instance containing repository info
        since: Only fetch events since this timestamp (defaults to last_sync or None)
        full_sync: If True, ignore since/last_sync and fetch all commits

    Returns:
        SyncResult with statistics about the sync operation
    """
    result = SyncResult()
    project = integration.project

    # Build the repository URL to filter by
    repository_url = f"https://github.com/{integration.repository_owner}/{integration.repository_name}"

    # Use last_sync if since is not provided (unless full_sync is requested)
    if not full_sync and since is None and integration.last_sync:
        since = integration.last_sync

    monitoring_service_url = getattr(settings, "MONITORING_SERVICE_URL", "http://localhost:8001")
    api_endpoint = f"{monitoring_service_url}/monitoring/api/git-events/"

    try:
        # Build request parameters
        params = {
            "repository_url": repository_url,
            "event_type": "commit",
            "limit": 500,
        }

        if since:
            params["since"] = since.isoformat()

        logger.info(f"Calling monitoring service at {api_endpoint} for {repository_url}")

        # Call monitoring service API
        response = requests.get(
            api_endpoint,
            params=params,
            timeout=30,
        )

        if response.status_code != 200:
            error_msg = f"Monitoring service ({api_endpoint}) returned status {response.status_code}"
            result.errors.append(error_msg)
            logger.error(f"Failed to fetch git events: {response.text[:500]}")
            return result

        data = response.json()
        git_events = data.get("git_events", [])

        logger.info(f"Fetched {len(git_events)} git events from monitoring service for {repository_url}")

        # Create CodeCommit records for each git event
        for event in git_events:
            try:
                commit_hash = event.get("commit_hash")
                if not commit_hash:
                    result.commits_skipped += 1
                    continue

                # Check if commit already exists
                if CodeCommit.objects.filter(project=project, commit_hash=commit_hash).exists():
                    result.commits_skipped += 1
                    continue

                # Parse timestamp
                timestamp_str = event.get("timestamp")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    timestamp = timezone.now()

                # Create CodeCommit record
                CodeCommit.objects.create(
                    project=project,
                    commit_hash=commit_hash,
                    author_email=event.get("author_email") or "unknown@example.com",
                    author_name=event.get("author_name") or "Unknown",
                    message=event.get("commit_message") or "",
                    branch=event.get("branch_name") or "main",
                    timestamp=timestamp,
                    files_changed=event.get("files_changed") or 0,
                    insertions=event.get("insertions") or 0,
                    deletions=event.get("deletions") or 0,
                )
                result.commits_created += 1

            except IntegrityError:
                # Commit already exists (race condition)
                result.commits_skipped += 1
            except Exception as e:
                result.errors.append(f"Error creating commit {event.get('commit_hash', 'unknown')}: {str(e)}")
                logger.error(f"Error creating CodeCommit: {e}")

    except requests.RequestException as e:
        error_msg = f"Failed to connect to monitoring service ({api_endpoint}): {str(e)}"
        result.errors.append(error_msg)
        logger.error(error_msg)

    return result


def sync_from_github_api(
    integration: GitHubIntegration,
    since: Optional[datetime] = None,
    branch: Optional[str] = None,
    full_sync: bool = False,
) -> SyncResult:
    """
    Sync commits directly from GitHub API.

    Args:
        integration: GitHubIntegration instance with repository info and access token
        since: Only fetch commits since this timestamp
        branch: Branch to fetch commits from (defaults to repository's default branch)
        full_sync: If True, ignore since/last_sync and fetch all commits

    Returns:
        SyncResult with statistics about the sync operation
    """
    result = SyncResult()
    project = integration.project

    if not integration.access_token:
        result.errors.append("No access token configured for this integration")
        return result

    # Use last_sync if since is not provided (unless full_sync is requested)
    if not full_sync and since is None and integration.last_sync:
        since = integration.last_sync

    # GitHub API endpoint for commits
    api_url = f"https://api.github.com/repos/{integration.repository_owner}/{integration.repository_name}/commits"

    headers = {
        "Authorization": f"token {integration.access_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    params = {"per_page": 100}

    if since:
        params["since"] = since.isoformat()

    if branch:
        params["sha"] = branch

    try:
        # Paginate through commits - limit pages to prevent timeout
        page = 1
        max_pages = 3 if full_sync else 10  # Limit pages for full sync to prevent timeout
        commits_to_create = []

        while True:
            params["page"] = page
            response = requests.get(api_url, headers=headers, params=params, timeout=30)

            if response.status_code == 401:
                error_msg = f"GitHub authentication failed for {integration.repository_owner}/{integration.repository_name} - token may be invalid or expired. Please re-authenticate with GitHub."
                result.errors.append(error_msg)
                logger.error(error_msg)
                break

            if response.status_code == 404:
                error_msg = f"Repository {integration.repository_owner}/{integration.repository_name} not found or no access with current token"
                result.errors.append(error_msg)
                logger.error(error_msg)
                break

            if response.status_code != 200:
                error_msg = f"GitHub API returned status {response.status_code} for {integration.repository_owner}/{integration.repository_name}"
                result.errors.append(error_msg)
                logger.error(f"GitHub API error: {response.text[:500]}")
                break

            commits = response.json()

            if not commits:
                break

            logger.info(f"Fetched {len(commits)} commits from GitHub API (page {page})")

            # Get existing commit hashes in bulk for efficiency
            existing_hashes = set(
                CodeCommit.objects.filter(
                    project=project,
                    commit_hash__in=[c.get("sha") for c in commits if c.get("sha")]
                ).values_list("commit_hash", flat=True)
            )

            for commit_data in commits:
                try:
                    commit_hash = commit_data.get("sha")
                    if not commit_hash:
                        result.commits_skipped += 1
                        continue

                    # Check if commit already exists
                    if commit_hash in existing_hashes:
                        result.commits_skipped += 1
                        continue

                    # Extract commit info
                    commit_info = commit_data.get("commit", {})
                    author_info = commit_info.get("author", {})
                    stats = commit_data.get("stats", {})

                    # Parse timestamp
                    date_str = author_info.get("date")
                    if date_str:
                        timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    else:
                        timestamp = timezone.now()

                    # Prepare CodeCommit object for bulk creation
                    commits_to_create.append(CodeCommit(
                        project=project,
                        commit_hash=commit_hash,
                        author_email=author_info.get("email") or "unknown@example.com",
                        author_name=author_info.get("name") or "Unknown",
                        message=commit_info.get("message") or "",
                        branch=branch or "main",
                        timestamp=timestamp,
                        files_changed=len(commit_data.get("files", [])) if "files" in commit_data else 0,
                        insertions=stats.get("additions", 0),
                        deletions=stats.get("deletions", 0),
                    ))

                except Exception as e:
                    result.errors.append(f"Error preparing commit {commit_data.get('sha', 'unknown')}: {str(e)}")
                    logger.error(f"Error preparing CodeCommit from GitHub: {e}")

            # Check if there are more pages
            if len(commits) < 100:
                break
            page += 1

            # Safety limit to prevent timeout
            if page > max_pages:
                logger.warning(f"Reached maximum page limit ({max_pages}) for GitHub API pagination")
                break

        # Bulk create all commits at once for better performance
        if commits_to_create:
            try:
                created = CodeCommit.objects.bulk_create(commits_to_create, ignore_conflicts=True)
                result.commits_created = len(created)
                logger.info(f"Bulk created {len(created)} commits from GitHub API")
            except Exception as e:
                result.errors.append(f"Error bulk creating commits: {str(e)}")
                logger.error(f"Error bulk creating commits: {e}")

    except requests.RequestException as e:
        result.errors.append(f"Failed to connect to GitHub API: {str(e)}")
        logger.error(f"Failed to connect to GitHub API: {e}")

    return result


def sync_integration(
    integration: GitHubIntegration,
    sync_monitoring: bool = True,
    sync_github: bool = True,
    since: Optional[datetime] = None,
    full_sync: bool = False,
) -> dict:
    """
    Sync commits from both monitoring service and GitHub API.

    Args:
        integration: GitHubIntegration instance
        sync_monitoring: Whether to sync from monitoring service
        sync_github: Whether to sync from GitHub API
        since: Only fetch commits since this timestamp
        full_sync: If True, ignore since/last_sync and fetch all commits

    Returns:
        Dictionary with sync results from both sources
    """
    results = {
        "monitoring": None,
        "github": None,
        "total_created": 0,
        "total_skipped": 0,
        "total_errors": 0,
    }

    if sync_monitoring:
        logger.info(f"Syncing from monitoring service for {integration}")
        monitoring_result = sync_from_monitoring_service(integration, since, full_sync=full_sync)
        results["monitoring"] = {
            "commits_created": monitoring_result.commits_created,
            "commits_skipped": monitoring_result.commits_skipped,
            "errors": monitoring_result.errors,
        }
        results["total_created"] += monitoring_result.commits_created
        results["total_skipped"] += monitoring_result.commits_skipped
        results["total_errors"] += len(monitoring_result.errors)

    if sync_github:
        logger.info(f"Syncing from GitHub API for {integration}")
        github_result = sync_from_github_api(integration, since, full_sync=full_sync)
        results["github"] = {
            "commits_created": github_result.commits_created,
            "commits_skipped": github_result.commits_skipped,
            "errors": github_result.errors,
        }
        results["total_created"] += github_result.commits_created
        results["total_skipped"] += github_result.commits_skipped
        results["total_errors"] += len(github_result.errors)

    # Update last_sync timestamp
    integration.last_sync = timezone.now()
    integration.save(update_fields=["last_sync"])

    logger.info(
        f"Sync completed for {integration}: "
        f"Created {results['total_created']}, Skipped {results['total_skipped']}, "
        f"Errors {results['total_errors']}"
    )

    return results


def sync_all_project_integrations(project: Project, **kwargs) -> list:
    """
    Sync all GitHub integrations for a project.

    Args:
        project: Project instance
        **kwargs: Arguments passed to sync_integration

    Returns:
        List of sync results for each integration
    """
    results = []

    for integration in project.github_integrations.filter(is_active=True):
        result = sync_integration(integration, **kwargs)
        result["integration_id"] = str(integration.id)
        result["repository"] = f"{integration.repository_owner}/{integration.repository_name}"
        results.append(result)

    return results
