import uuid

from django.db import models


class Device(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="devices")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    token = models.CharField(max_length=512, unique=True)
    name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["platform", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.platform}:{self.is_active}"


class NotificationPreference(models.Model):
    class Category(models.TextChoices):
        PARTNER_INVITATION = "partner_invitation", "Partner invitation"
        PARTNER_JOINED = "partner_joined", "Partner joined"
        TOPIC_COMPLETED = "topic_completed", "Topic completed"
        ANALYSIS_READY = "analysis_ready", "Analysis ready"
        PACT_APPROVAL_REQUIRED = "pact_approval_required", "Pact approval required"
        PACT_ACTIVATED = "pact_activated", "Pact activated"
        ACCOUNT_DELETION_REQUESTED = "account_deletion_requested", "Account deletion requested"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notification_preferences")
    category = models.CharField(max_length=64, choices=Category.choices)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "category"], name="unique_notification_preference_per_user_category"),
        ]
        indexes = [
            models.Index(fields=["user", "enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.category}:{self.enabled}"


class Notification(models.Model):
    class Status(models.TextChoices):
        UNREAD = "unread", "Unread"
        READ = "read", "Read"
        SUPPRESSED = "suppressed", "Suppressed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    couple = models.ForeignKey("couples.Couple", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=64, choices=NotificationPreference.Category.choices)
    event_key = models.CharField(max_length=255)
    title = models.CharField(max_length=180)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNREAD)
    read_at = models.DateTimeField(null=True, blank=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "event_key"], name="unique_notification_event_per_user"),
        ]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
            models.Index(fields=["category", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.category}:{self.status}"


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SUPPRESSED = "suppressed", "Suppressed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="notification_deliveries")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=80, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "device"], name="unique_notification_delivery_per_device"),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["device", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_id}:{self.device_id}:{self.status}"
