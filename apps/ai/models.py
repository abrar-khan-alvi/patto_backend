import uuid

from django.db import models


class AIPromptVersion(models.Model):
    key = models.CharField(max_length=120)
    version = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255, blank=True)
    system_prompt = models.TextField()
    developer_prompt = models.TextField(blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "version"], name="unique_ai_prompt_key_version"),
        ]
        indexes = [
            models.Index(fields=["key", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.key}:v{self.version}"


class AIAnalysisResult(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        REFUSED = "refused", "Refused"
        FAILED = "failed", "Failed"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis_job = models.OneToOneField(
        "responses.TopicAnalysisJob",
        on_delete=models.CASCADE,
        related_name="ai_result",
    )
    prompt_version = models.ForeignKey(
        AIPromptVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="analysis_results",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    model = models.CharField(max_length=120)
    provider_response_id = models.CharField(max_length=255, blank=True)
    schema_name = models.CharField(max_length=120, default="topic_analysis")
    output = models.JSONField(null=True, blank=True)
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
            models.Index(fields=["model", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.analysis_job_id}:{self.status}"


class AIFollowUpQuestion(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        SKIPPED = "skipped", "Skipped"
        REFUSED = "refused", "Refused"
        FAILED = "failed", "Failed"
        INVALID_OUTPUT = "invalid_output", "Invalid output"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "responses.TopicSession",
        on_delete=models.CASCADE,
        related_name="ai_follow_ups",
    )
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="ai_follow_ups")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="ai_follow_ups")
    prompt_version = models.ForeignKey(
        AIPromptVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="follow_up_questions",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    model = models.CharField(max_length=120)
    provider_response_id = models.CharField(max_length=255, blank=True)
    topic_stable_key = models.CharField(max_length=160)
    topic_version = models.PositiveSmallIntegerField()
    follow_up_question = models.TextField(blank=True)
    internal_reason = models.TextField(blank=True)
    skip = models.BooleanField(default=False)
    skip_reason = models.TextField(blank=True)
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
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_ai_follow_up_per_session_user"),
        ]
        indexes = [
            models.Index(fields=["session", "user"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:{self.user_id}:{self.status}"


class AISafetyEvent(models.Model):
    class Stage(models.TextChoices):
        INPUT = "input", "Input"
        OUTPUT = "output", "Output"

    class Category(models.TextChoices):
        ABUSE_COERCION = "abuse_coercion", "Abuse or coercion"
        SELF_HARM = "self_harm", "Self-harm"
        THREAT = "threat", "Threat"
        SEXUAL_CONTENT = "sexual_content", "Sexual content"
        MINORS = "minors", "Minors"
        MEDICAL_LEGAL = "medical_legal", "Medical or legal"
        PROMPT_INJECTION = "prompt_injection", "Prompt injection"

    class Severity(models.TextChoices):
        SAFE = "safe", "Safe"
        CAUTION = "caution", "Caution"
        HIGH = "high", "High"
        BLOCKED = "blocked", "Blocked"

    class Route(models.TextChoices):
        NORMAL = "normal", "Normal AI task"
        RESTRICTED_SAFETY = "restricted_safety", "Restricted safety response"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis_job = models.ForeignKey(
        "responses.TopicAnalysisJob",
        on_delete=models.CASCADE,
        related_name="safety_events",
    )
    stage = models.CharField(max_length=20, choices=Stage.choices)
    category = models.CharField(max_length=64, choices=Category.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    route = models.CharField(max_length=32, choices=Route.choices)
    detector = models.CharField(max_length=80, default="local_policy_v1")
    content_fingerprint = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["analysis_job", "stage"]),
            models.Index(fields=["category", "severity", "created_at"]),
            models.Index(fields=["route", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.analysis_job_id}:{self.stage}:{self.category}:{self.severity}"
