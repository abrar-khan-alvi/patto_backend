import uuid

from django.db import models


class TopicSession(models.Model):
    class TopicKind(models.TextChoices):
        BUILT_IN = "built_in", "Built-in"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="topic_sessions")
    topic_kind = models.CharField(max_length=20, choices=TopicKind.choices)
    topic_stable_key = models.CharField(max_length=160)
    topic_version = models.PositiveSmallIntegerField()
    expected_question_count = models.PositiveSmallIntegerField()
    built_in_topic = models.ForeignKey(
        "topics.Topic",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    custom_topic = models.ForeignKey(
        "topics.CoupleTopic",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["couple", "topic_kind", "topic_stable_key", "topic_version"],
                name="unique_topic_session_per_couple_topic_version",
            ),
        ]
        indexes = [
            models.Index(fields=["couple", "topic_kind"]),
            models.Index(fields=["topic_stable_key", "topic_version"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.topic_kind}:{self.topic_stable_key}:v{self.topic_version}"


class TopicResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TopicSession, on_delete=models.CASCADE, related_name="responses")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="topic_responses")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="topic_responses")
    built_in_question = models.ForeignKey(
        "topics.Question",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    custom_question = models.ForeignKey(
        "topics.CustomQuestion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    question_stable_key = models.CharField(max_length=160)
    question_version = models.PositiveSmallIntegerField()
    selected_option_key = models.CharField(max_length=160, blank=True)
    text_answer = models.TextField(blank=True)
    answered_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "user", "question_stable_key", "question_version"],
                name="unique_response_per_user_question_version",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "user"]),
            models.Index(fields=["couple", "user"]),
            models.Index(fields=["question_stable_key", "question_version"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:{self.user_id}:{self.question_stable_key}"


class TopicMemberCompletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TopicSession, on_delete=models.CASCADE, related_name="completions")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="topic_completions")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="topic_completions")
    completed_at = models.DateTimeField()
    locked_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_topic_completion_per_member"),
        ]
        indexes = [
            models.Index(fields=["session", "completed_at"]),
            models.Index(fields=["couple", "user"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:{self.user_id}:completed"


class TopicAnalysisJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(TopicSession, on_delete=models.CASCADE, related_name="analysis_job")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="topic_analysis_jobs")
    triggered_by_completion = models.ForeignKey(
        TopicMemberCompletion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggered_analysis_jobs",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    queued_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "status", "queued_at"]),
            models.Index(fields=["status", "queued_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:{self.status}"


class TopicSyncEvent(models.Model):
    class EventType(models.TextChoices):
        PARTNER_COMPLETED_WAITING = "partner_completed_waiting", "Partner completed, waiting for you"
        ANALYSIS_QUEUED = "analysis_queued", "Analysis queued"
        ANALYSIS_READY = "analysis_ready", "Analysis ready"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TopicSession, on_delete=models.CASCADE, related_name="sync_events")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="topic_sync_events")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="topic_sync_events")
    event_type = models.CharField(max_length=64, choices=EventType.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "user", "event_type"],
                name="unique_topic_sync_event_per_user_type",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "event_type"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id}:{self.user_id}:{self.event_type}"
