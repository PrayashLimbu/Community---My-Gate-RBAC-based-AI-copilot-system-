# api/views.py
from firebase_admin import messaging
from .models import FCMDevice, CustomUser
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import generics  
from .serializers import FCMDeviceSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from .ai_tools import AICopilotService
from .models import Visitor, Event, CustomUser
from .ai_tools import AICopilotService
from .serializers import (
    MyTokenObtainPairSerializer, 
    VisitorSerializer, 
    EventSerializer,
    UserManagementSerializer
)
from .permissions import (
    IsResident, 
    IsAdminOrGuard, 
    IsResidentOrAdmin, 
    IsAdmin,
    IsGuard
)

# --- Auth View (from Phase 2) ---
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


# --- Audit Log View (NEW) ---
class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to view the immutable audit log.
    Only Admins can view this.
    """
    queryset = Event.objects.all().order_by('-timestamp')
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]


# --- Visitor View (UPDATED) ---
class VisitorViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Visitors.
    """
    queryset = Visitor.objects.all().order_by('-created_at')
    serializer_class = VisitorSerializer

    def _log_event(self, type, actor, visitor, payload=None):
        """Helper function to create an audit event."""
        Event.objects.create(
            type=type,
            actor=actor,
            subject_visitor=visitor,
            payload=payload or {}
        )

    def get_permissions(self):
        """
        Assign permissions based on action.
        """
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsResident]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated, IsResident | IsAdminOrGuard]
        elif self.action in ['approve', 'deny']:
            permission_classes = [permissions.IsAuthenticated, IsResidentOrAdmin]
        elif self.action in ['checkin', 'checkout']:
            permission_classes = [permissions.IsAuthenticated, IsAdminOrGuard]
        else:
            # For other actions (update, partial_update, destroy)
            permission_classes = [permissions.IsAuthenticated, IsAdmin] 
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """
        Filter the queryset based on user role.
        """
        user = self.request.user
        
        if user.role == CustomUser.Role.RESIDENT:
            return Visitor.objects.filter(host_household=user.household)
        elif user.role in [CustomUser.Role.GUARD, CustomUser.Role.ADMIN]:
            return Visitor.objects.all().order_by('-created_at')
        
        return Visitor.objects.none()

    def perform_create(self, serializer):
        """
        Automatically set the host_household and log the event.
        """
        if self.request.user.role == CustomUser.Role.RESIDENT:
            visitor = serializer.save(
                host_household=self.request.user.household, 
                status=Visitor.Status.PENDING
            )
            self._log_event(
                Event.EventType.VISITOR_CREATED, 
                self.request.user, 
                visitor
            )
    def _send_fcm_to_user(self, user, title, body, data=None):
        """Helper to send FCM message to a single user."""
        devices = FCMDevice.objects.filter(user=user)
        tokens = [device.registration_id for device in devices]
        if not tokens:
            print(f"No FCM tokens for user {user.username}") # <-- THIS IS THE LOG WE'RE LOOKING FOR
            return
        
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=tokens,
            data=data or {}
        )
        try:
            response = messaging.send_multicast(message)
            print(f'Sent FCM to {response.success_count} device(s) for user {user.username}') # <-- OR THIS
        except Exception as e:
            print(f"Error sending FCM for user {user.username}: {e}")

    # --- STATE MACHINE ACTIONS ---

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Action for a Resident or Admin to approve a PENDING visitor.
        """
        visitor = self.get_object()
        user = request.user
        
        # 1. State Machine Check
        if visitor.status != Visitor.Status.PENDING:
            return Response(
                {'error': 'Visitor is not in a PENDING state.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 2. Permission Check (extra layer)
        if user.role == CustomUser.Role.RESIDENT and user.household != visitor.host_household:
             return Response(
                {'error': 'You can only approve visitors for your own household.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 3. Apply Change
        visitor.status = Visitor.Status.APPROVED
        visitor.approved_by = user
        visitor.approved_at = timezone.now()
        visitor.save()
        
        # 4. Log Event
        self._log_event(Event.EventType.VISITOR_APPROVED, user, visitor)
        
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_200_OK)

        guards = CustomUser.objects.filter(role=CustomUser.Role.GUARD)
        for guard in guards:
            self._send_fcm_to_user(
                user=guard,
                title="Visitor Approved",
                body=f"'{visitor.name}' for {visitor.host_household.flat_number} is now approved."
            )
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def deny(self, request, pk=None):
        """
        Action for a Resident or Admin to deny a PENDING visitor.
        """
        visitor = self.get_object()
        user = request.user
        reason = request.data.get('reason', 'No reason provided')
        
        if visitor.status != Visitor.Status.PENDING:
            return Response(
                {'error': 'Visitor is not in a PENDING state.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if user.role == CustomUser.Role.RESIDENT and user.household != visitor.host_household:
             return Response(
                {'error': 'You can only deny visitors for your own household.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        visitor.status = Visitor.Status.DENIED
        visitor.save()
        
        self._log_event(
            Event.EventType.VISITOR_DENIED, 
            user, 
            visitor, 
            {'reason': reason}
        )
        
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def checkin(self, request, pk=None):
        """
        Action for a Guard or Admin to check-in an APPROVED visitor.
        """
        visitor = self.get_object()
        user = request.user
        
        if visitor.status != Visitor.Status.APPROVED:
            return Response(
                {'error': 'Visitor must be APPROVED to be checked in.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        visitor.status = Visitor.Status.CHECKED_IN
        visitor.checked_in_at = timezone.now()
        visitor.save()
        
        self._log_event(Event.EventType.VISITOR_CHECKIN, user, visitor)
        for resident in visitor.host_household.members.all():
             self._send_fcm_to_user(
                user=resident,
                title="Visitor Arrived",
                body=f"'{visitor.name}' has checked in."
            )
        
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """
        Action for a Guard or Admin to check-out a CHECKED_IN visitor.
        """
        visitor = self.get_object()
        user = request.user
        
        if visitor.status != Visitor.Status.CHECKED_IN:
            return Response(
                {'error': 'Visitor must be CHECKED_IN to be checked out.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        visitor.status = Visitor.Status.CHECKED_OUT
        visitor.checked_out_at = timezone.now()
        visitor.save()
        
        self._log_event(Event.EventType.VISITOR_CHECKOUT, user, visitor)
        
        return Response(VisitorSerializer(visitor).data, status=status.HTTP_200_OK)
class ChatbotView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Expect a 'history' array instead of 'message' string
        history = request.data.get('history')
        if not history or not isinstance(history, list):
            return Response(
                {'error': 'Message history is required and must be an array.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = AICopilotService(user=request.user)
        
        # Pass the whole history list to the service
        response_message = service.process_message(history)
        
        return Response({'reply': response_message}, status=status.HTTP_200_OK)
class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Admins to view and manage all users.
    """
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
class RegisterFCMDeviceView(generics.CreateAPIView):
    """
    POST-only endpoint for clients to register their FCM device token.
    Saves the token and associates it with the authenticated user.
    """
    queryset = FCMDevice.objects.all()
    serializer_class = FCMDeviceSerializer
    permission_classes = [permissions.IsAuthenticated] # Any logged-in user can register

    def get_serializer_context(self):
        # Pass request to serializer so we can get the user
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context