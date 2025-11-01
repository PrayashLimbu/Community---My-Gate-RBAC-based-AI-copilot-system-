# api/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import CustomUser, Household, Visitor, Event  # <-- THIS LINE IS CRITICAL
from .models import FCMDevice
#
# --- Auth Serializers (from Phase 2) ---
#
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['role'] = user.role 
        
        if user.role == 'RESIDENT':
             token['household_id'] = user.household_id

        return token

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'phone', 'role', 'household')


#
# --- Visitor Management Serializers (from Phase 3) ---
#
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
        model = Visitor
        fields = [
            'id', 'name', 'phone', 'purpose', 'status', 
            'host_household', 'host_household_id', 'scheduled_time', 
            'created_at', 'checked_in_at', 'checked_out_at'
        ]
        # Status and host_household are set by the system, not by direct user input
        read_only_fields = ['status', 'host_household']

class EventSerializer(serializers.ModelSerializer):
    # Show the username of the actor, not just their ID
    actor = serializers.StringRelatedField()

    class Meta:
        model = Event
        fields = ['id', 'type', 'timestamp', 'actor', 'subject_visitor', 'payload']
class UserManagementSerializer(serializers.ModelSerializer):
    """
    Serializer for Admins to manage user details,
    including role and household.
    """
    # Show household flat number, not just ID
    household_flat_number = serializers.CharField(source='household.flat_number', read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'phone', 'role',
            'household', # This is the ID (writeable)
            'household_flat_number', # This is the flat number (read-only)
            'first_name', 'last_name'
        ]
        # Allow admins to change these fields
        read_only_fields = ['id', 'username', 'household_flat_number']
class FCMDeviceSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = FCMDevice
        fields = ['id', 'user', 'registration_id', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        # Use get_or_create to prevent duplicate tokens for the same user
        device, created = FCMDevice.objects.get_or_create(
            user=user, 
            registration_id=validated_data['registration_id']
        )
        return device