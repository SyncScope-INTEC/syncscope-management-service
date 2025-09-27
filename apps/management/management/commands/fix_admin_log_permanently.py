"""
Permanently fix django_admin_log user_id type mismatch.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Permanently fix django_admin_log user_id type mismatch"

    def handle(self, *args, **options):
        """Fix the admin log table permanently."""

        with connection.cursor() as cursor:
            self.stdout.write("=== Fixing django_admin_log permanently ===")

            # Clear all existing admin log entries
            self.stdout.write("Clearing existing admin log entries...")
            cursor.execute("DELETE FROM django_admin_log;")

            # Check auth_user.id type
            cursor.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'auth_user' AND column_name = 'id'
            """
            )
            auth_user_id_type = cursor.fetchone()[0]
            self.stdout.write(f"auth_user.id type: {auth_user_id_type}")

            # Check current django_admin_log.user_id type
            cursor.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'django_admin_log' AND column_name = 'user_id'
            """
            )
            admin_log_user_id_type = cursor.fetchone()[0]
            self.stdout.write(f"django_admin_log.user_id type: {admin_log_user_id_type}")

            if auth_user_id_type == admin_log_user_id_type:
                self.stdout.write("✅ Types already match - no fix needed")
                return

            # Drop foreign key constraint
            self.stdout.write("Dropping foreign key constraint...")
            cursor.execute(
                """
                ALTER TABLE django_admin_log
                DROP CONSTRAINT IF EXISTS django_admin_log_user_id_fkey CASCADE;
            """
            )

            # Change the column type to match auth_user.id
            if auth_user_id_type in ["uuid"]:
                self.stdout.write("Converting user_id to UUID...")
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ALTER COLUMN user_id TYPE UUID USING NULL;
                """
                )
                # Add foreign key to auth.users (UUID)
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ADD CONSTRAINT django_admin_log_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES auth.users(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
                """
                )
            else:
                # auth_user_id_type is integer/bigint
                self.stdout.write("Converting user_id to integer...")
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ALTER COLUMN user_id TYPE integer USING NULL;
                """
                )
                # Add foreign key to auth_user (integer)
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ADD CONSTRAINT django_admin_log_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
                """
                )

            self.stdout.write("✅ django_admin_log fixed permanently!")
            self.stdout.write("Admin panels should now work without UUID/integer errors.")
