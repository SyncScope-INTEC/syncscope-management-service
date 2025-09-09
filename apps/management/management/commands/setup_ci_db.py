"""
Management command to set up database for CI/test environments
"""

import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Set up database for CI/test environments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-schema",
            action="store_true",
            help="Create auth schema if it does not exist",
        )
        parser.add_argument(
            "--force-public-schema",
            action="store_true",
            help="Force using public schema for CI (overrides auth schema setting)",
        )
        parser.add_argument(
            "--run-migrations",
            action="store_true",
            help="Run database migrations after setup",
        )

    def handle(self, *args, **options):
        """Handle the command execution"""

        # Show current database configuration
        self.show_database_config()

        # Decide on schema strategy
        if options["force_public_schema"]:
            self.setup_public_schema_ci()
        else:
            # Try auth schema first, fallback to public
            try:
                if options["create_schema"] or self.should_use_auth_schema():
                    self.create_auth_schema()
                    if options["run_migrations"]:
                        self.run_migrations()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Auth schema setup failed: {e}"))
                self.stdout.write(self.style.WARNING("Falling back to public schema for CI..."))
                self.setup_public_schema_ci()

        # Check if database connection works
        self.check_database_connection()

        # Verify tables exist
        self.verify_required_tables()

        self.stdout.write(self.style.SUCCESS("✓ Database setup completed for CI environment"))

    def show_database_config(self):
        """Show current database configuration"""
        self.stdout.write("Current database configuration:")

        db_config = settings.DATABASES["default"]
        self.stdout.write(f"  - Engine: {db_config.get('ENGINE', 'Not set')}")
        self.stdout.write(f"  - Name: {db_config.get('NAME', 'Not set')}")
        self.stdout.write(f"  - Host: {db_config.get('HOST', 'Not set')}")
        self.stdout.write(f"  - Port: {db_config.get('PORT', 'Not set')}")
        self.stdout.write(f"  - User: {db_config.get('USER', 'Not set')}")

        options = db_config.get("OPTIONS", {})
        if "options" in options:
            self.stdout.write(f"  - PostgreSQL options: {options['options']}")
            if "search_path=auth" in options["options"]:
                self.stdout.write(self.style.WARNING("  ⚠️  Using auth schema"))
            else:
                self.stdout.write(self.style.SUCCESS("  ✓ Using public schema (recommended for CI)"))
        else:
            self.stdout.write("  - No PostgreSQL options set")

        self.stdout.write(f"  - DEBUG mode: {settings.DEBUG}")
        self.stdout.write("")

    def create_auth_schema(self):
        """Create auth schema if it doesn't exist"""
        self.stdout.write("Creating auth schema if it does not exist...")

        try:
            with connection.cursor() as cursor:
                # Create auth schema if it doesn't exist
                cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")

            self.stdout.write(self.style.SUCCESS("✓ Auth schema created or already exists"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error creating auth schema: {e}"))
            # Don't raise in CI environments, just warn
            self.stdout.write(self.style.WARNING("⚠️  Continuing without auth schema (using public schema)"))

    def check_database_connection(self):
        """Check if database connection works"""
        self.stdout.write("Checking database connection...")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] == 1:
                    self.stdout.write(self.style.SUCCESS("✓ Database connection successful"))
                else:
                    raise Exception("Unexpected result from test query")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Database connection failed: {e}"))
            raise

    def should_use_auth_schema(self):
        """Determine if we should use auth schema based on environment"""
        # Check if we're in CI environment
        ci_indicators = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "TRAVIS", "CIRCLECI"]
        is_ci = any(os.environ.get(indicator) for indicator in ci_indicators)

        if is_ci:
            self.stdout.write("🔍 CI environment detected")
            # Check if auth schema is configured
            db_config = settings.DATABASES["default"]
            options = db_config.get("OPTIONS", {})
            uses_auth_schema = "search_path=auth" in options.get("options", "")

            if uses_auth_schema:
                self.stdout.write("📋 Auth schema is configured, attempting to use it")
                return True
            else:
                self.stdout.write("📋 Public schema is configured")
                return False
        else:
            self.stdout.write("🏠 Local environment detected")
            return True  # Use auth schema for local development

    def setup_public_schema_ci(self):
        """Set up CI to use public schema instead of auth schema"""
        self.stdout.write("🔧 Setting up CI to use public schema...")

        try:
            # Temporarily modify database settings to use public schema
            db_config = settings.DATABASES["default"]
            if "OPTIONS" in db_config and "options" in db_config["OPTIONS"]:
                original_options = db_config["OPTIONS"]["options"]
                # Remove auth schema setting for CI
                db_config["OPTIONS"]["options"] = original_options.replace("-c search_path=auth", "")
                self.stdout.write("✓ Temporarily switched to public schema for CI")

            # Run migrations in public schema
            self.run_migrations()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to setup public schema: {e}"))
            raise

    def run_migrations(self):
        """Run database migrations"""
        self.stdout.write("🔄 Running database migrations...")

        try:
            # Run migrations
            call_command("migrate", verbosity=1, interactive=False)
            self.stdout.write(self.style.SUCCESS("✓ Database migrations completed"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Migration failed: {e}"))
            raise

    def verify_required_tables(self):
        """Verify that required tables exist in the database"""
        self.stdout.write("🔍 Verifying required tables exist...")

        # These are the actual table names used by the models
        required_tables = ["users", "user_sessions", "companies"]

        try:
            with connection.cursor() as cursor:
                # Get all table names
                cursor.execute(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = CURRENT_SCHEMA()
                """
                )
                existing_tables = [row[0] for row in cursor.fetchall()]

                self.stdout.write(f"📋 Found {len(existing_tables)} tables in current schema")

                missing_tables = []
                for table in required_tables:
                    if table in existing_tables:
                        self.stdout.write(f"  ✓ {table}")
                    else:
                        missing_tables.append(table)
                        self.stdout.write(f"  ❌ {table} (missing)")

                if missing_tables:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  {len(missing_tables)} required tables are missing: {', '.join(missing_tables)}"
                        )
                    )
                    self.stdout.write("💡 Consider running migrations or checking schema configuration")
                else:
                    self.stdout.write(self.style.SUCCESS("✅ All required tables found"))

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️  Could not verify tables: {e}"))
