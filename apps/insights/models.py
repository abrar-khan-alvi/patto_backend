import uuid

from django.db import models


class MonthlyInsight(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        INELIGIBLE = "ineligible", "Ineligible"
        SUCCEEDED = "succeeded", "Succeeded"
        REFUSED = "refused", "Refused"
        FAILED = "failed", "Failed"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="monthly_insights")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    input_start_date = models.DateField()
    input_end_date = models.DateField()
    minimum_revealed_days = models.PositiveSmallIntegerField(default=3)
    revealed_day_count = models.PositiveSmallIntegerField(default=0)
    prompt_version = models.ForeignKey(
        "ai.AIPromptVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="monthly_insights",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    model = models.CharField(max_length=120, blank=True)
    provider_response_id = models.CharField(max_length=255, blank=True)
    schema_name = models.CharField(max_length=120, default="monthly_insight")
    sections = models.JSONField(default=dict, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    usage = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    refusal_reason = models.TextField(blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["couple", "year", "month"], name="unique_monthly_insight_per_couple_month"),
            models.CheckConstraint(check=models.Q(month__gte=1, month__lte=12), name="monthly_insight_month_range"),
        ]
        indexes = [
            models.Index(fields=["couple", "year", "month"]),
            models.Index(fields=["status", "queued_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.year}-{self.month:02d}:{self.status}"


class MonthlyInsightInput(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insight = models.ForeignKey(MonthlyInsight, on_delete=models.CASCADE, related_name="inputs")
    assignment = models.ForeignKey("daily.DailyAssignment", on_delete=models.PROTECT, related_name="monthly_insight_inputs")
    answer = models.ForeignKey("daily.DailyAnswer", on_delete=models.PROTECT, related_name="monthly_insight_inputs")
    local_date = models.DateField()
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="monthly_insight_inputs")
    question_stable_key = models.CharField(max_length=120)
    question_prompt = models.TextField()
    text_answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["insight", "answer"], name="unique_monthly_insight_input_answer"),
        ]
        indexes = [
            models.Index(fields=["insight", "local_date"]),
            models.Index(fields=["assignment", "user"]),
        ]

    def __str__(self) -> str:
        return f"{self.insight_id}:{self.local_date}:{self.user_id}"
