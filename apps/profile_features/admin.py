from django.contrib import admin

from apps.common.admin import REDACTED_ADMIN_VALUE, SensitiveContentAdminMixin
from apps.profile_features.models import (
    AccountDeletionRequest,
    DataExportRequest,
    Referral,
    ReferralCode,
    ReferralReward,
    SubscriptionManagementRequest,
    SupportTicket,
    SupportTicketMessage,
)


class SupportTicketMessageInline(admin.TabularInline):
    model = SupportTicketMessage
    extra = 0
    readonly_fields = ("id", "sender_type", "user", "body", "created_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category", "subject", "status", "created_at")
    list_filter = ("category", "status")
    search_fields = ("id", "user__email", "subject")
    inlines = [SupportTicketMessageInline]


admin.site.register(ReferralCode)
admin.site.register(Referral)
admin.site.register(ReferralReward)
admin.site.register(SubscriptionManagementRequest)


@admin.register(DataExportRequest)
class DataExportRequestAdmin(SensitiveContentAdminMixin, admin.ModelAdmin):
    safe_fields = ("id", "user", "status", "checksum_sha256", "byte_size", "requested_at", "completed_at", "failure_reason")
    sensitive_fields = ("export_data",)
    redacted_field_names = ("redacted_export_data",)
    list_display = ("id", "user", "status", "byte_size", "requested_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("id", "user__email", "checksum_sha256")
    readonly_fields = ("id", "export_data", "requested_at", "completed_at")

    @admin.display(description="Export data")
    def redacted_export_data(self, obj):
        return REDACTED_ADMIN_VALUE


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "couple_action", "scheduled_for", "processed_at", "completed_at")
    list_filter = ("status", "couple_action")
    search_fields = ("id", "user__email")
    readonly_fields = (
        "id",
        "requested_at",
        "sessions_revoked_at",
        "billing_updated_at",
        "partner_notified_at",
        "processed_at",
        "completed_at",
    )
