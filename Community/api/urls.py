from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    MyTokenObtainPairView, 
    VisitorViewSet, 
    EventViewSet,
    ChatbotView,
    UserViewSet,
    RegisterFCMDeviceView  # <-- IMPORT THIS
)
# ... (other imports) ...

router = DefaultRouter()
router.register(r'visitors', VisitorViewSet, basename='visitor')
router.register(r'events', EventViewSet, basename='event')
router.register(r'users', UserViewSet, basename='user') # <-- 2. REGISTER NEW ROUTE

urlpatterns = [
    # Auth endpoints
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # AI Chat endpoint
    path('chat/', ChatbotView.as_view(), name='chat'), # <-- ADD THIS LINE

    path('register-fcm/', RegisterFCMDeviceView.as_view(), name='register-fcm'), # <-- 2. Add
    
    # API endpoints
    path('', include(router.urls)),
]