"""
Django management command to check database health for serverless deployments
"""

import sys

from django.core.management.base import BaseCommand

from config.database_retry import DatabaseHealthCheck


class Command(BaseCommand):
    help = "Check database connection health for serverless environments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Skip cache and force fresh health check",
        )
        parser.add_argument(
            "--retry-count",
            type=int,
            default=3,
            help="Number of retries if health check fails",
        )

    def handle(self, *args, **options):
        use_cache = not options["no_cache"]
        retry_count = options["retry_count"]

        self.stdout.write("Checking database health...")

        for attempt in range(retry_count):
            try:
                is_healthy = DatabaseHealthCheck.is_healthy(use_cache=use_cache)

                if is_healthy:
                    self.stdout.write(self.style.SUCCESS(f"✓ Database is healthy (attempt {attempt + 1})"))
                    sys.exit(0)
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Database health check failed (attempt {attempt + 1}/{retry_count})")
                    )

                    if attempt < retry_count - 1:
                        self.stdout.write("Retrying...")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Database health check error (attempt {attempt + 1}): {e}"))

                if attempt < retry_count - 1:
                    self.stdout.write("Retrying...")

        self.stdout.write(self.style.ERROR(f"❌ Database is unhealthy after {retry_count} attempts"))
        sys.exit(1)
