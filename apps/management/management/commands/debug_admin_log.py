"""
Debug command to check admin log configuration and fix it.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Debug and fix admin log configuration"

    def handle(self, *args, **options):
        """Debug current admin log state and fix if needed."""

        with connection.cursor() as cursor:
            self.stdout.write("=== Database Environment Analysis ===")

            # Check current schema
            cursor.execute("SELECT current_schema();")
            current_schema = cursor.fetchone()[0]
            self.stdout.write(f"Current schema: {current_schema}")

            # Check for auth.users table
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'auth' AND table_name = 'users'
                );
            """
            )
            auth_users_exists = cursor.fetchone()[0]
            self.stdout.write(f"auth.users table exists: {auth_users_exists}")

            # Check for auth_user table
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'auth_user'
                );
            """
            )
            auth_user_exists = cursor.fetchone()[0]
            self.stdout.write(f"auth_user table exists: {auth_user_exists}")

            # Check django_admin_log table
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'django_admin_log'
                );
            """
            )
            admin_log_exists = cursor.fetchone()[0]
            self.stdout.write(f"django_admin_log table exists: {admin_log_exists}")

            if admin_log_exists:
                # Check admin log user_id type
                cursor.execute(
                    """
                    SELECT data_type FROM information_schema.columns
                    WHERE table_name = 'django_admin_log' AND column_name = 'user_id'
                """
                )
                user_id_type = cursor.fetchone()[0]
                self.stdout.write(f"django_admin_log.user_id type: {user_id_type}")

                # Check foreign key constraints
                cursor.execute(
                    """
                    SELECT
                        conname,
                        pg_get_constraintdef(oid)
                    FROM pg_constraint
                    WHERE conrelid = 'django_admin_log'::regclass
                    AND contype = 'f';
                """
                )
                constraints = cursor.fetchall()
                self.stdout.write("Foreign key constraints:")
                for constraint in constraints:
                    self.stdout.write(f"  {constraint[0]}: {constraint[1]}")

            self.stdout.write("\n=== Fix Analysis ===")

            if auth_users_exists and admin_log_exists:
                # Check if we need to fix the admin log
                cursor.execute(
                    """
                    SELECT data_type FROM information_schema.columns
                    WHERE table_name = 'django_admin_log' AND column_name = 'user_id'
                """
                )
                current_type = cursor.fetchone()[0]

                if current_type == "uuid":
                    self.stdout.write("✅ Admin log already has UUID user_id")

                    # Check if constraint points to correct table
                    cursor.execute(
                        """
                        SELECT pg_get_constraintdef(oid)
                        FROM pg_constraint
                        WHERE conrelid = 'django_admin_log'::regclass
                        AND contype = 'f'
                        AND conname LIKE '%user_id%';
                    """
                    )
                    constraint_def = cursor.fetchone()
                    if constraint_def:
                        self.stdout.write(f"Current constraint: {constraint_def[0]}")
                        if "auth.users" in constraint_def[0]:
                            self.stdout.write("✅ Constraint points to auth.users")
                        else:
                            self.stdout.write("❌ Constraint points to wrong table")
                    else:
                        self.stdout.write("❌ No user_id foreign key constraint found")

                elif current_type == "integer":
                    self.stdout.write("❌ Admin log still has integer user_id - needs fixing")

                    # Apply the fix
                    self.stdout.write("Applying fix...")
                    cursor.execute("DELETE FROM django_admin_log;")
                    cursor.execute(
                        "ALTER TABLE django_admin_log DROP CONSTRAINT IF EXISTS django_admin_log_user_id_fkey CASCADE;"
                    )
                    cursor.execute("ALTER TABLE django_admin_log ALTER COLUMN user_id TYPE UUID USING NULL;")
                    cursor.execute(
                        """
                        ALTER TABLE django_admin_log
                        ADD CONSTRAINT django_admin_log_user_id_fkey
                        FOREIGN KEY (user_id) REFERENCES auth.users(id)
                        ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
                    """
                    )
                    self.stdout.write("✅ Fix applied successfully")
            else:
                self.stdout.write("❌ Missing required tables for fix")
