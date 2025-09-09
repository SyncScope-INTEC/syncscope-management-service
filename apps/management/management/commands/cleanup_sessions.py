"""
Django management command to cleanup expired sessions
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.authentication.models import UserSession
from config.database_retry import database_retry


class Command(BaseCommand):
    help = "Cleanup expired user sessions with retry logic"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    @database_retry(max_retries=3)
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("Cleaning up expired sessions...")

        # Count expired sessions
        expired_count = UserSession.objects.filter(expires_at__lt=timezone.now()).count()

        if expired_count == 0:
            self.stdout.write(self.style.SUCCESS("✓ No expired sessions found"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would delete {expired_count} expired sessions"))
            return

        try:
            UserSession.cleanup_expired_sessions()
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully cleaned up {expired_count} expired sessions"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error cleaning up sessions: {e}"))
            raise
