from django.contrib import admin

from apps.common.models import AuditEvent, IdempotencyKey
from apps.common.services import record_audit_event


SENSITIVE_CONTENT_ACCESS_GROUP = "Sensitive Content Access"
REDACTED_ADMIN_VALUE = "Restricted. Sensitive content access is required."


def has_sensitive_admin_access(request) -> bool:
    user = getattr(request, "user", None)
    if user is None or not user.is_active or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=SENSITIVE_CONTENT_ACCESS_GROUP).exists()


class SensitiveContentAdminMixin:
    sensitive_fields: tuple[str, ...] = ()
    safe_fields: tuple[str, ...] = ()
    redacted_field_names: tuple[str, ...] = ()
    sensitive_audit_action = "admin.sensitive_content_viewed"

    def user_can_view_sensitive_content(self, request) -> bool:
        return has_sensitive_admin_access(request)

    def get_fields(self, request, obj=None):
        if not self.safe_fields:
            return super().get_fields(request, obj)
        if self.user_can_view_sensitive_content(request):
            return [*self.safe_fields, *self.sensitive_fields]
        return [*self.safe_fields, *self.redacted_field_names]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if self.user_can_view_sensitive_content(request):
            readonly.extend(field for field in self.sensitive_fields if field not in readonly)
        else:
            readonly.extend(field for field in self.redacted_field_names if field not in readonly)
        return readonly

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id and self.user_can_view_sensitive_content(request):
            obj = self.get_object(request, object_id)
            if obj is not None:
                record_audit_event(
                    action=self.sensitive_audit_action,
                    actor=request.user,
                    target=obj,
                    metadata={"admin_model": obj._meta.label_lower},
                )
        return super().changeform_view(request, object_id, form_url, extra_context)


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = [field.name for field in self.model._meta.fields]
        return [*fields, *super().get_readonly_fields(request, obj)]


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "request_id", "created_at")
    list_filter = ("action", "target_type")
    search_fields = ("action", "actor__email", "target_type", "target_id", "request_id")
    readonly_fields = ("id", "actor", "action", "target_type", "target_id", "request_id", "metadata", "created_at", "updated_at")


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("key", "user", "request_method", "request_path", "response_status_code", "locked_until", "created_at")
    list_filter = ("request_method", "response_status_code")
    search_fields = ("key", "user__email", "request_path")
    readonly_fields = ("id", "key", "user", "request_path", "request_method", "request_hash", "response_status_code", "response_body", "locked_until", "created_at", "updated_at")
