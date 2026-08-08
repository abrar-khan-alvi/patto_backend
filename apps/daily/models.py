import uuid

from django.conf import settings
from django.db import models


class DailyQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stable_key = models.SlugField(max_length=120, unique=True)
    prompt = models.TextField()
    category = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "stable_key"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
            models.Index(fields=["category", "sort_order"]),
        ]

    def __str__(self) -> str:
        return self.stable_key


class DailyAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        REVEALED = "revealed", "Revealed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="daily_assignments")
    question = models.ForeignKey(DailyQuestion, on_delete=models.PROTECT, related_name="assignments")
    local_date = models.DateField()
    timezone = models.CharField(max_length=64, default="UTC")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["couple", "local_date"], name="unique_daily_assignment_per_couple_date"),
        ]
        indexes = [
            models.Index(fields=["couple", "local_date"]),
            models.Index(fields=["status", "local_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id} {self.local_date}"


class DailyAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(DailyAssignment, on_delete=models.CASCADE, related_name="answers")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="daily_answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_answers")
    text_answer = models.TextField()
    answered_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assignment", "user"], name="unique_daily_answer_per_user_assignment"),
        ]
        indexes = [
            models.Index(fields=["assignment", "user"]),
            models.Index(fields=["couple", "answered_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.assignment_id} {self.user_id}"


class DailyReveal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(DailyAssignment, on_delete=models.CASCADE, related_name="reveal")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="daily_reveals")
    revealed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "revealed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.assignment_id} revealed"


class CoupleStreak(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.OneToOneField("couples.Couple", on_delete=models.CASCADE, related_name="daily_streak")
    current_count = models.PositiveIntegerField(default=0)
    longest_count = models.PositiveIntegerField(default=0)
    last_completed_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.couple_id}: {self.current_count}"
