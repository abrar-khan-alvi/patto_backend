import uuid

from django.db import models
from django.db.models import Q


class Couple(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"
        DISSOLVED = "dissolved", "Dissolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_couples")
    activated_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    dissolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["created_by", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.id} {self.status}"


class CoupleMember(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        LEFT = "left", "Left"
        REMOVED = "removed", "Removed"

    class Role(models.TextChoices):
        PARTNER_1 = "partner_1", "Partner 1"
        PARTNER_2 = "partner_2", "Partner 2"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="couple_memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["couple", "user"], name="unique_member_per_couple"),
            models.UniqueConstraint(
                fields=["couple", "role"],
                condition=Q(status="active"),
                name="unique_active_role_per_couple",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="active"),
                name="unique_active_couple_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["couple", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.couple_id} {self.role}"


class PartnerInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="invitations")
    invited_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sent_partner_invitations",
    )
    email = models.EmailField()
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_partner_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "created_at"]),
            models.Index(fields=["email", "created_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["accepted_at"]),
            models.Index(fields=["revoked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} {self.couple_id}"


class Entitlement(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        APPLE_IAP = "apple_iap", "Apple In-App Purchase"
        GOOGLE_IAP = "google_iap", "Google In-App Purchase"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey(Couple, on_delete=models.CASCADE, related_name="entitlements")
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.MANUAL)
    external_reference = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "starts_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["revoked_at"]),
        ]

    def is_active(self, at=None) -> bool:
        from django.utils import timezone

        current_time = at or timezone.now()
        if self.revoked_at is not None:
            return False
        if self.starts_at > current_time:
            return False
        if self.expires_at is not None and self.expires_at <= current_time:
            return False
        return True
