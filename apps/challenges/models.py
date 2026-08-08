import uuid

from django.conf import settings
from django.db import models


class Challenge(models.Model):
    class Source(models.TextChoices):
        CURATED = "curated", "Curated"
        FALLBACK = "fallback", "Fallback"
        AI_SUGGESTED = "ai_suggested", "AI suggested"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stable_key = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField()
    instructions = models.TextField(blank=True)
    category = models.CharField(max_length=80, blank=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.CURATED)
    duration_days = models.PositiveSmallIntegerField(default=1)
    safety_policy_version = models.CharField(max_length=40, default="challenge_policy_v1")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "stable_key"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
            models.Index(fields=["source", "is_active"]),
            models.Index(fields=["category", "sort_order"]),
        ]

    def __str__(self) -> str:
        return self.stable_key


class ChallengeAssignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    class AssignmentSource(models.TextChoices):
        CURATED = "curated", "Curated"
        FALLBACK = "fallback", "Fallback"
        AI_SUGGESTED = "ai_suggested", "AI suggested"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="challenge_assignments")
    challenge = models.ForeignKey(Challenge, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_challenges",
    )
    source = models.CharField(max_length=32, choices=AssignmentSource.choices, default=AssignmentSource.CURATED)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    starts_on = models.DateField()
    due_on = models.DateField(null=True, blank=True)
    suggested_payload = models.JSONField(default=dict, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    fallback_reason = models.CharField(max_length=160, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "status", "created_at"]),
            models.Index(fields=["source", "created_at"]),
            models.Index(fields=["starts_on", "due_on"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.challenge_id}:{self.status}"


class ChallengeMemberCompletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(ChallengeAssignment, on_delete=models.CASCADE, related_name="member_completions")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="challenge_completions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_completions")
    note = models.TextField(blank=True)
    completed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assignment", "user"], name="unique_challenge_completion_per_assignment_user"),
        ]
        indexes = [
            models.Index(fields=["assignment", "user"]),
            models.Index(fields=["couple", "completed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.assignment_id}:{self.user_id}"
