import uuid

from django.db import models


class DiscussionThread(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="discussion_threads")
    session = models.ForeignKey(
        "responses.TopicSession",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="discussion_threads",
    )
    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discussion_threads",
    )
    title = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_discussion_threads")
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "status", "created_at"]),
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["analysis_run", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.title or self.id}"


class DiscussionMessage(models.Model):
    class SenderType(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "AI"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name="messages")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="discussion_messages")
    author = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discussion_messages",
    )
    sender_type = models.CharField(max_length=20, choices=SenderType.choices)
    body = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["couple", "created_at"]),
            models.Index(fields=["sender_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.sender_type}:{self.created_at}"


class MediationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name="mediation_requests")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="mediation_requests")
    requested_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="mediation_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    context_message_count = models.PositiveIntegerField(default=0)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread", "status", "created_at"]),
            models.Index(fields=["couple", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.thread_id}:{self.status}"


class MediationResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(MediationRequest, on_delete=models.CASCADE, related_name="response")
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name="mediation_responses")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="mediation_responses")
    message = models.OneToOneField(
        DiscussionMessage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mediation_response",
    )
    content = models.TextField()
    model = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.request_id}:response"
