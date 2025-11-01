# api/permissions.py
from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """Allows access only to Admin users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')

class IsGuard(BasePermission):
    """Allows access only to Guard users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'GUARD')

class IsResident(BasePermission):
    """Allows access only to Resident users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'RESIDENT')

class IsAdminOrGuard(BasePermission):
    """Allows access to Admin or Guard users."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(request.user.role == 'ADMIN' or request.user.role == 'GUARD')
class IsResidentOrAdmin(BasePermission):
    """Allows access to Resident or Admin users."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(request.user.role == 'RESIDENT' or request.user.role == 'ADMIN')
        