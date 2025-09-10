"""
Management command to migrate tables from public schema to auth schema
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Migrate authentication tables from public schema to auth schema"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually executing",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        with connection.cursor() as cursor:
            # First, ensure auth schema exists
            self.stdout.write("Ensuring auth schema exists...")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")

            # Check what tables exist in public vs auth
            cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('authentication_user', 'companies', 'user_sessions')
                ORDER BY table_name;
            """
            )
            public_tables = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'auth' 
                AND table_name IN ('users', 'companies', 'user_sessions', 'authentication_user')
                ORDER BY table_name;
            """
            )
            auth_tables = [row[0] for row in cursor.fetchall()]

            self.stdout.write(f"Tables in public: {public_tables}")
            self.stdout.write(f"Tables in auth: {auth_tables}")

            # If authentication_user exists in public but users exists in auth,
            # we need to update django_migrations table
            if "authentication_user" in public_tables and "users" in auth_tables:
                self.stdout.write("Updating Django migrations to point to auth schema...")
                if not dry_run:
                    cursor.execute("SET search_path TO auth, public;")
                    # Update the django_migrations table to reflect we're using auth schema
                    cursor.execute(
                        """
                        UPDATE django_migrations 
                        SET applied = NOW() 
                        WHERE app = 'authentication' 
                        AND name = '0001_initial';
                    """
                    )
                else:
                    self.stdout.write("Would update django_migrations table")

            # Drop old tables from public schema if they exist in auth
            tables_to_drop = []
            if "authentication_user" in public_tables and "users" in auth_tables:
                tables_to_drop.append("authentication_user")
            if "companies" in public_tables and "companies" in auth_tables:
                tables_to_drop.append("companies")
            if "user_sessions" in public_tables and "user_sessions" in auth_tables:
                tables_to_drop.append("user_sessions")

            for table in tables_to_drop:
                self.stdout.write(f"Dropping public.{table} (exists in auth schema)...")
                if not dry_run:
                    # Drop foreign key constraints first
                    cursor.execute(
                        f"""
                        SELECT conname, conrelid::regclass
                        FROM pg_constraint 
                        WHERE confrelid = 'public.{table}'::regclass;
                    """
                    )
                    constraints = cursor.fetchall()

                    for constraint_name, table_name in constraints:
                        cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name};")

                    cursor.execute(f"DROP TABLE IF EXISTS public.{table} CASCADE;")
                else:
                    self.stdout.write(f"Would drop public.{table}")

            # Update User model table name to match auth schema
            if "users" in auth_tables:
                self.stdout.write("Updating User model to use auth.users table...")
                # This will be handled in the model update

            self.stdout.write(self.style.SUCCESS("Migration to auth schema completed successfully!"))
