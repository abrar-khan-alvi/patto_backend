import uuid

from django.conf import settings
from django.db import models


class CoachConversation(models.Model):
    class Scope(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COUPLE = "couple", "Couple"
        CONFLICT = "conflict", "Conflict"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    couple = models.ForeignKey("couples.Couple", null=True, blank=True, on_delete=models.CASCADE, related_name="coach_conversations")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_coach_conversations")
    title = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    metadata = models.JSONField(default=dict, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "scope", "status", "created_at"]),
            models.Index(fields=["couple", "scope", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.id}"


class CoachParticipant(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        PARTNER = "partner", "Partner"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(CoachConversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_participations")
    role = models.CharField(max_length=20, choices=Role.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="unique_coach_participant_per_conversation_user"),
        ]
        indexes = [
            models.Index(fields=["user", "conversation"]),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id}:{self.user_id}:{self.role}"


class CoachMessage(models.Model):
    class SenderType(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "AI"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(CoachConversation, on_delete=models.CASCADE, related_name="messages")
    couple = models.ForeignKey("couples.Couple", null=True, blank=True, on_delete=models.CASCADE, related_name="coach_messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="coach_messages")
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    body = models.TextField()
    render_as = models.CharField(max_length=20, default="text")
    explicitly_shared_with_partner = models.BooleanField(default=False)
    shared_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["author", "explicitly_shared_with_partner"]),
            models.Index(fields=["couple", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id}:{self.sender_type}:{self.created_at}"


class CoachRun(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        REFUSED = "refused", "Refused"
        FAILED = "failed", "Failed"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(CoachConversation, on_delete=models.CASCADE, related_name="runs")
    couple = models.ForeignKey("couples.Couple", null=True, blank=True, on_delete=models.CASCADE, related_name="coach_runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_runs")
    prompt_version = models.ForeignKey("ai.AIPromptVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="coach_runs")
    status = models.CharField(max_length=32, choices=Status.choices)
    model = models.CharField(max_length=120)
    provider_response_id = models.CharField(max_length=255, blank=True)
    response_message = models.ForeignKey(CoachMessage, null=True, blank=True, on_delete=models.SET_NULL, related_name="coach_runs")
    context_message_ids = models.JSONField(default=list, blank=True)
    output = models.JSONField(default=dict, blank=True)
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
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id}:{self.status}"
