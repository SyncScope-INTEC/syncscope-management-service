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

            # Check what user table exists and get its id type
            cursor.execute("""
                SELECT table_name, data_type
                FROM information_schema.columns
                WHERE (table_name = 'auth_user' OR (table_schema = 'auth' AND table_name = 'users'))
                AND column_name = 'id'
                ORDER BY table_name
            """)
            user_tables = cursor.fetchall()

            self.stdout.write(f"Found user tables: {user_tables}")

            # Determine which user table to use
            if any(table[0] == 'users' for table in user_tables):
                # auth.users exists (UUID)
                user_table = 'auth.users'
                auth_user_id_type = next(table[1] for table in user_tables if table[0] == 'users')
            else:
                # Use auth_user (integer)
                user_table = 'auth_user'
                auth_user_id_type = next(table[1] for table in user_tables if table[0] == 'auth_user')

            self.stdout.write(f"Using {user_table} with id type: {auth_user_id_type}")

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

            # Drop ALL foreign key constraints on user_id
            self.stdout.write("Dropping all foreign key constraints on user_id...")
            cursor.execute("""
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'django_admin_log'::regclass
                AND contype = 'f'
                AND confkey[1] = (
                    SELECT attnum
                    FROM pg_attribute
                    WHERE attrelid = 'django_admin_log'::regclass
                    AND attname = 'user_id'
                )
            """)
            constraints = cursor.fetchall()

            for constraint in constraints:
                constraint_name = constraint[0]
                self.stdout.write(f"Dropping constraint: {constraint_name}")
                cursor.execute(f"ALTER TABLE django_admin_log DROP CONSTRAINT {constraint_name} CASCADE;")

            # Change the column type to match auth_user.id
            if auth_user_id_type in ["uuid"]:
                self.stdout.write("Converting user_id to UUID...")
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ALTER COLUMN user_id TYPE UUID USING NULL;
                """
                )
                # Add foreign key to the correct table
                cursor.execute(f"""
                    ALTER TABLE django_admin_log
                    ADD CONSTRAINT django_admin_log_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES {user_table}(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
                """)
            else:
                # auth_user_id_type is integer/bigint
                self.stdout.write("Converting user_id to integer...")
                cursor.execute(
                    """
                    ALTER TABLE django_admin_log
                    ALTER COLUMN user_id TYPE integer USING NULL;
                """
                )
                # Add foreign key to the correct table
                cursor.execute(f"""
                    ALTER TABLE django_admin_log
                    ADD CONSTRAINT django_admin_log_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES {user_table}(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
                """)

            self.stdout.write("✅ django_admin_log fixed permanently!")
            self.stdout.write("Admin panels should now work without UUID/integer errors.")
