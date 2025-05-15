from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if request.user.is_staff:
                return True
            return obj.user == request.user
        
        return obj.user == request.user or request.user.is_staff