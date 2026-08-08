import uuid

from django.conf import settings
from django.db import models


class ReferralCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.code


class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REWARDED = "rewarded", "Rewarded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name="referrals")
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referrals_sent")
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_received")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    verified_subscription = models.ForeignKey("billing.Subscription", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_referrals")
    verified_event = models.ForeignKey("billing.SubscriptionEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_referrals")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]


class ReferralReward(models.Model):
    class Status(models.TextChoices):
        GRANTED = "granted", "Granted"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.OneToOneField(Referral, on_delete=models.CASCADE, related_name="reward")
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="referral_rewards")
    source_event = models.ForeignKey("billing.SubscriptionEvent", on_delete=models.PROTECT, related_name="referral_rewards")
    reward_type = models.CharField(max_length=80, default="iap_referral_credit")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GRANTED)
    metadata = models.JSONField(default=dict, blank=True)
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WAITING = "waiting", "Waiting"
        CLOSED = "closed", "Closed"

    class Category(models.TextChoices):
        ACCOUNT = "account", "Account"
        BILLING = "billing", "Billing"
        TECHNICAL = "technical", "Technical"
        SAFETY = "safety", "Safety"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
    category = models.CharField(max_length=40, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=180)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
        ]


class SupportTicketMessage(models.Model):
    class SenderType(models.TextChoices):
        USER = "user", "User"
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="support_ticket_messages")
    sender_type = models.CharField(max_length=20, choices=SenderType.choices, default=SenderType.USER)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class SubscriptionManagementRequest(models.Model):
    class RequestType(models.TextChoices):
        STATUS_HELP = "status_help", "Status help"
        RESTORE_HELP = "restore_help", "Restore help"
        CANCEL_HELP = "cancel_help", "Cancel help"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription_management_requests")
    couple = models.ForeignKey("couples.Couple", null=True, blank=True, on_delete=models.SET_NULL, related_name="subscription_management_requests")
    request_type = models.CharField(max_length=40, choices=RequestType.choices)
    platform = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DataExportRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_export_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    export_data = models.JSONField(default=dict, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    byte_size = models.PositiveIntegerField(default=0)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)


class AccountDeletionRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CANCELED = "canceled", "Canceled"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"

    class CoupleAction(models.TextChoices):
        NONE = "none", "None"
        ARCHIVED = "archived", "Archived"
        DISSOLVED = "dissolved", "Dissolved"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_deletion_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField(blank=True)
    couple_action = models.CharField(max_length=20, choices=CoupleAction.choices, default=CoupleAction.NONE)
    requested_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField()
    sessions_revoked_at = models.DateTimeField(null=True, blank=True)
    billing_updated_at = models.DateTimeField(null=True, blank=True)
    partner_notified_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
