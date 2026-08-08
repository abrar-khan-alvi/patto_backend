from rest_framework.permissions import BasePermission


class IsSelf(BasePermission):
    message = "You can only access your own resource."

    def has_object_permission(self, request, view, obj):
        return obj == request.user
