from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Debug user authentication issues"

    def handle(self, *args, **options):
        self.stdout.write("Debugging user authentication...")

        # Check total users
        total_users = User.objects.count()
        self.stdout.write(f"Total users in database: {total_users}")

        # List all users
        self.stdout.write("\nAll users:")
        for user in User.objects.all():
            self.stdout.write(f"  ID: {user.id}")
            self.stdout.write(f"  Email: {user.email}")
            self.stdout.write(f"  First name: {user.first_name}")
            self.stdout.write(f"  Last name: {user.last_name}")
            self.stdout.write(f"  Is active: {user.is_active}")
            self.stdout.write(f"  Is staff: {user.is_staff}")
            self.stdout.write(f"  Is superuser: {user.is_superuser}")
            self.stdout.write(f"  Password set: {bool(user.password)}")
            self.stdout.write(f"  Company: {user.company}")
            self.stdout.write("  ---")

        # Test specific email lookup
        test_emails = input("\nEnter email to test (or press Enter to skip): ").strip()
        if test_emails:
            try:
                user = User.objects.get(email=test_emails)
                self.stdout.write(f"✅ Found user: {user}")
                self.stdout.write(
                    f"Password check available: {hasattr(user, 'check_password')}"
                )
            except User.DoesNotExist:
                self.stdout.write(f"❌ User with email '{test_emails}' not found")
            except Exception as e:
                self.stdout.write(f"❌ Error looking up user: {e}")
