# Community/api/management/commands/create_test_users.py

from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import CustomUser, Household, Visitor # <-- 1. Import Visitor
from django.utils import timezone # <-- 2. Import timezone

class Command(BaseCommand):
    help = 'Creates seed users (admin, guard, resident) and 1 pending visitor'

    def handle(self, *args, **options):
        self.stdout.write("Starting to create seed users...")
        
        # --- 1. Admin User ---
        admin_username = 'Roku' 
        try:
            admin_user = CustomUser.objects.get(username=admin_username)
            admin_user.role = CustomUser.Role.ADMIN
            if not admin_user.email:
                admin_user.email = f"{admin_username}@example.com"
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Updated '{admin_username}' user to ADMIN role."))
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Admin user '{admin_username}' not found. "
                "Please create it first with 'createsuperuser' and re-run this command."
            ))
            return

        # --- 2. Guard User ---
        guard_username = 'guard1'
        try:
            CustomUser.objects.get(username=guard_username)
            self.stdout.write(f"User '{guard_username}' already exists. Skipping.")
        except CustomUser.DoesNotExist:
            CustomUser.objects.create_user(
                username=guard_username,
                password='guardpassword',
                email=f"{guard_username}@example.com",
                role=CustomUser.Role.GUARD,
                is_staff=True 
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully created GUARD user '{guard_username}'."))

        # --- 3. Resident User & Household ---
        try:
            household = Household.objects.get(flat_number='F-101')
        except Household.DoesNotExist:
            household = Household.objects.create(flat_number='F-101', name='The Patels')
            self.stdout.write(self.style.SUCCESS(f"Successfully created household '{household.flat_number}'."))

        resident_username = 'resident1'
        try:
            resident_user = CustomUser.objects.get(username=resident_username)
            self.stdout.write(f"User '{resident_username}' already exists. Skipping.")
        except CustomUser.DoesNotExist:
            resident_user = CustomUser.objects.create_user(
                username=resident_username,
                password='residentpassword',
                email=f"{resident_username}@example.com",
                role=CustomUser.Role.RESIDENT,
                household=household
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully created RESIDENT user '{resident_username}'."))

        # --- 4. Pending Visitor (THE NEW PART) ---
        visitor_name = "Ramesh (Seed)"
        try:
            Visitor.objects.get(name=visitor_name, host_household=resident_user.household)
            self.stdout.write(f"Visitor '{visitor_name}' already exists. Skipping.")
        except Visitor.DoesNotExist:
            Visitor.objects.create(
                name=visitor_name,
                phone="1234567890",
                purpose="Delivery",
                host_household=resident_user.household,
                status=Visitor.Status.PENDING,
                scheduled_time=timezone.now() # Schedule for today
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully created PENDING visitor '{visitor_name}'."))

        self.stdout.write(self.style.SUCCESS("Seed script finished."))