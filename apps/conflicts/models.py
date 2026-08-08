import uuid

from django.conf import settings
from django.db import models


class ConflictThread(models.Model):
    class Status(models.TextChoices):
        COLLECTING = "collecting", "Collecting perspectives"
        PERSPECTIVES_LOCKED = "perspectives_locked", "Perspectives locked"
        BRIDGE_READY = "bridge_ready", "Bridge ready"
        DISCUSSION_OPEN = "discussion_open", "Discussion open"
        RESOLVED = "resolved", "Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_threads")
    title = models.CharField(max_length=180)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.COLLECTING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_conflict_threads")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.title}"


class ConflictPerspective(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ConflictThread, on_delete=models.CASCADE, related_name="perspectives")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_perspectives")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conflict_perspectives")
    situation = models.TextField()
    feelings = models.TextField(blank=True)
    needs = models.TextField(blank=True)
    requested_outcome = models.TextField(blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_conflict_perspective_per_thread_user"),
        ]
        indexes = [
            models.Index(fields=["thread", "user"]),
            models.Index(fields=["couple", "locked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.user_id}"


class ConflictBridge(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        REFUSED = "refused", "Refused"
        FAILED = "failed", "Failed"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"
        POLICY_BLOCKED = "policy_blocked", "Policy blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.OneToOneField(ConflictThread, on_delete=models.CASCADE, related_name="bridge")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_bridges")
    prompt_version = models.ForeignKey("ai.AIPromptVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="conflict_bridges")
    status = models.CharField(max_length=32, choices=Status.choices)
    model = models.CharField(max_length=120)
    provider_response_id = models.CharField(max_length=255, blank=True)
    neutral_summary = models.TextField(blank=True)
    common_ground = models.JSONField(default=list, blank=True)
    partner_summaries = models.JSONField(default=dict, blank=True)
    next_steps = models.JSONField(default=list, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    refusal_reason = models.TextField(blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["couple", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.status}"


class ConflictMessage(models.Model):
    class SenderType(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "AI"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ConflictThread, on_delete=models.CASCADE, related_name="messages")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="conflict_messages")
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    body = models.TextField()
    render_as = models.CharField(max_length=20, default="text")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["couple", "created_at"]),
        ]


class ConflictMediation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(ConflictThread, on_delete=models.CASCADE, related_name="mediations")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_mediations")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conflict_mediations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    prompt = models.TextField(blank=True)
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConflictResolution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.OneToOneField(ConflictThread, on_delete=models.CASCADE, related_name="resolution")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="conflict_resolutions")
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conflict_resolutions")
    summary = models.TextField()
    proposed_pact_changes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "created_at"]),
        ]
