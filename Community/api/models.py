# api/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers



class Household(models.Model):
    flat_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True) # e.g., "The Patels"

    def __str__(self):
        return self.flat_number


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        RESIDENT = 'RESIDENT', _('Resident')
        GUARD = 'GUARD', _('Guard')
        ADMIN = 'ADMIN', _('Admin')

    # We nullify email/phone as we might use one or the other
    email = models.EmailField(_('email address'), unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RESIDENT)
    household = models.ForeignKey(Household, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')

    # Use email or phone as the username field
    # USERNAME_FIELD = 'email' # or 'phone'
    # REQUIRED_FIELDS = []



class Visitor(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        DENIED = 'DENIED', _('Denied')
        CHECKED_IN = 'CHECKED_IN', _('Checked In')
        CHECKED_OUT = 'CHECKED_OUT', _('Checked Out')

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Link to the host who invited them
    host_household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name='visitors')

    # Scheduling
    scheduled_time = models.DateTimeField(null=True, blank=True)

    # Approval details
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_visitors')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} for {self.host_household.flat_number}"

class HouseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = ['id', 'flat_number', 'name']

class VisitorSerializer(serializers.ModelSerializer):
    # Make host_household read-only, we'll set it automatically
    host_household = HouseholdSerializer(read_only=True)
    
    # We'll use this to show the host household's ID
    host_household_id = serializers.PrimaryKeyRelatedField(
        queryset=Household.objects.all(), 
        source='host_household', 
        write_only=True
    )

    class Meta:
        model =Visitor
        fields = [
            'id', 'name', 'phone', 'purpose', 'status', 
            'host_household', 'host_household_id', 'scheduled_time', 
            'created_at', 'checked_in_at', 'checked_out_at'
        ]
        # Status and host_household are set by the system, not by direct user input
        read_only_fields = ['status', 'host_household']
        
class Event(models.Model):
    # Per [cite: 47]
    class EventType(models.TextChoices):
        VISITOR_CREATED = 'VISITOR_CREATED', _('Visitor Created')
        VISITOR_APPROVED = 'VISITOR_APPROVED', _('Visitor Approved')
        VISITOR_DENIED = 'VISITOR_DENIED', _('Visitor Denied')
        VISITOR_CHECKIN = 'VISITOR_CHECKIN', _('Visitor Checked In')
        VISITOR_CHECKOUT = 'VISITOR_CHECKOUT', _('Visitor Checked Out')
        ROLE_CHANGE = 'ROLE_CHANGE', _('Role Change')

    type = models.CharField(max_length=30, choices=EventType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)

    # The user who performed the action [cite: 47]
    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='acted_events')

    # The object of the action (e.g., the visitor, or the user whose role changed) [cite: 47]
    subject_visitor = models.ForeignKey(Visitor, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    subject_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='subject_events')

    # Store extra details as JSON [cite: 47]
    payload = models.JSONField(null=True, blank=True) 

    def __str__(self):
        return f"{self.type} by {self.actor} at {self.timestamp}"
class FCMDevice(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='fcm_devices')
    registration_id = models.TextField(unique=True) # The FCM token
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional: Add device info like type (web, android, ios), name, last_used

    def __str__(self):
        return f"{self.user.username}'s device ({self.registration_id[:10]}...)"