import uuid

from django.db import models


class IAPPurchaseAccount(models.Model):
    class Platform(models.TextChoices):
        APPLE = "apple", "Apple"
        GOOGLE = "google", "Google"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="iap_accounts")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="iap_accounts")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    app_account_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "app_account_token"],
                name="unique_iap_platform_app_account_token",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "platform"]),
            models.Index(fields=["couple", "platform"]),
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.user_id}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELED = "canceled", "Canceled"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="subscriptions")
    owner = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="owned_subscriptions")
    platform = models.CharField(max_length=20, choices=IAPPurchaseAccount.Platform.choices)
    product_id = models.CharField(max_length=255)
    original_transaction_id = models.CharField(max_length=255)
    latest_transaction_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    raw_latest_event = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "original_transaction_id"],
                name="unique_iap_original_transaction",
            ),
        ]
        indexes = [
            models.Index(fields=["couple", "status"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.original_transaction_id}:{self.status}"


class SubscriptionEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.CharField(max_length=20, choices=IAPPurchaseAccount.Platform.choices)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=80)
    payload_hash = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    processed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    subscription = models.ForeignKey(
        Subscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["platform", "event_id"], name="unique_iap_platform_event"),
        ]
        indexes = [
            models.Index(fields=["platform", "event_type"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.event_id}:{self.status}"
