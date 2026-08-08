import uuid

from django.db import models


class Topic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    stable_key = models.CharField(max_length=120, unique=True)
    icon = models.CharField(max_length=40, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    version = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "slug"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
            models.Index(fields=["stable_key", "version"]),
        ]

    def __str__(self) -> str:
        return self.slug


class TopicTranslation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=12)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["topic", "language"], name="unique_topic_translation_language"),
        ]
        indexes = [
            models.Index(fields=["language", "title"]),
        ]

    def __str__(self) -> str:
        return f"{self.topic.slug}:{self.language}"


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE_CHOICE_WITH_TEXT = "single_choice_with_text", "Single choice with text"
        TEXT = "text", "Text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="questions")
    stable_key = models.CharField(max_length=160)
    kind = models.CharField(max_length=40, choices=Kind.choices, default=Kind.SINGLE_CHOICE_WITH_TEXT)
    sort_order = models.PositiveSmallIntegerField()
    version = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["topic__sort_order", "sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["topic", "stable_key", "version"], name="unique_question_version"),
            models.UniqueConstraint(fields=["topic", "sort_order", "version"], name="unique_question_order_per_version"),
        ]
        indexes = [
            models.Index(fields=["topic", "is_active", "sort_order"]),
            models.Index(fields=["stable_key", "version"]),
        ]

    def __str__(self) -> str:
        return f"{self.topic.slug}:q{self.sort_order}:v{self.version}"


class QuestionTranslation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=12)
    prompt = models.TextField()
    open_text_prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["question", "language"], name="unique_question_translation_language"),
        ]
        indexes = [
            models.Index(fields=["language"]),
        ]

    def __str__(self) -> str:
        return f"{self.question_id}:{self.language}"


class QuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    stable_key = models.CharField(max_length=160)
    sort_order = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["question", "stable_key"], name="unique_question_option_key"),
            models.UniqueConstraint(fields=["question", "sort_order"], name="unique_question_option_order"),
        ]

    def __str__(self) -> str:
        return f"{self.question_id}:{self.stable_key}"


class QuestionOptionTranslation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    option = models.ForeignKey(QuestionOption, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=12)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["option", "language"], name="unique_question_option_translation_language"),
        ]
        indexes = [
            models.Index(fields=["language"]),
        ]

    def __str__(self) -> str:
        return f"{self.option_id}:{self.language}"


class CoupleTopic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="custom_topics")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_custom_topics")
    stable_key = models.CharField(max_length=160)
    icon = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    version = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="newer_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["couple", "stable_key", "version"], name="unique_couple_topic_version"),
        ]
        indexes = [
            models.Index(fields=["couple", "is_active"]),
            models.Index(fields=["stable_key", "version"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.stable_key}:v{self.version}"


class CustomQuestion(models.Model):
    class Kind(models.TextChoices):
        SINGLE_CHOICE_WITH_TEXT = "single_choice_with_text", "Single choice with text"
        TEXT = "text", "Text"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(CoupleTopic, on_delete=models.CASCADE, related_name="questions")
    stable_key = models.CharField(max_length=160)
    kind = models.CharField(max_length=40, choices=Kind.choices, default=Kind.SINGLE_CHOICE_WITH_TEXT)
    prompt = models.TextField()
    open_text_prompt = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField()
    version = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["topic", "stable_key", "version"], name="unique_custom_question_version"),
            models.UniqueConstraint(fields=["topic", "sort_order", "version"], name="unique_custom_question_order_version"),
        ]
        indexes = [
            models.Index(fields=["topic", "is_active", "sort_order"]),
            models.Index(fields=["stable_key", "version"]),
        ]

    def __str__(self) -> str:
        return f"{self.topic_id}:{self.stable_key}:v{self.version}"


class CustomQuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(CustomQuestion, on_delete=models.CASCADE, related_name="options")
    stable_key = models.CharField(max_length=160)
    text = models.TextField()
    sort_order = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["question", "stable_key"], name="unique_custom_question_option_key"),
            models.UniqueConstraint(fields=["question", "sort_order"], name="unique_custom_question_option_order"),
        ]

    def __str__(self) -> str:
        return f"{self.question_id}:{self.stable_key}"
