import uuid

from django.db import models


class AnalysisRun(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SAFETY_BLOCKED = "safety_blocked", "Safety blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey("responses.TopicSession", on_delete=models.CASCADE, related_name="analysis_runs")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="analysis_runs")
    analysis_job = models.ForeignKey("responses.TopicAnalysisJob", on_delete=models.CASCADE, related_name="domain_runs")
    ai_result = models.ForeignKey(
        "ai.AIAnalysisResult",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="domain_runs",
    )
    version = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices)
    topic_stable_key = models.CharField(max_length=160)
    topic_version = models.PositiveSmallIntegerField()
    active_member_ids = models.JSONField(default=list, blank=True)
    deterministic_similarity_score = models.PositiveSmallIntegerField(default=0)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "version"], name="unique_analysis_run_version_per_session"),
        ]
        indexes = [
            models.Index(fields=["session", "version"]),
            models.Index(fields=["couple", "status", "created_at"]),
            models.Index(fields=["analysis_job", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:v{self.version}:{self.status}"


class TopicAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.OneToOneField(AnalysisRun, on_delete=models.CASCADE, related_name="topic_analysis")
    summary = models.TextField()
    alignment_score = models.PositiveSmallIntegerField()
    confidence_score = models.PositiveSmallIntegerField(default=0)
    common_ground = models.JSONField(default=list, blank=True)
    differences = models.JSONField(default=list, blank=True)
    sensitive_areas = models.JSONField(default=list, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["alignment_score", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"topic-analysis:{self.run_id}"


class AlignmentDimension(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="alignment_dimensions")
    label = models.CharField(max_length=160)
    score = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.label}:{self.score}"


class ConversationStarter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="conversation_starters")
    prompt = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:starter:{self.sort_order}"


class ProposedClause(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        DISMISSED = "dismissed", "Dismissed"
        CONVERTED = "converted", "Converted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="proposed_clauses")
    clause_text = models.TextField()
    source = models.CharField(max_length=80, default="topic_analysis")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "sort_order"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:clause:{self.sort_order}"
