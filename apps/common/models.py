import uuid

from django.db import models


class UUIDTimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditEvent(UUIDTimeStampedModel):
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    request_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["request_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}".strip()


class IdempotencyKey(UUIDTimeStampedModel):
    key = models.CharField(max_length=255)
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
    )
    request_path = models.CharField(max_length=255)
    request_method = models.CharField(max_length=12)
    request_hash = models.CharField(max_length=128)
    response_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "user"], name="unique_idempotency_key_per_user"),
        ]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["locked_until"]),
        ]

    def __str__(self) -> str:
        return self.key
