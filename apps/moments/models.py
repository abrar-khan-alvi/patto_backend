import uuid

from django.conf import settings
from django.db import models


def moment_media_upload_path(instance, filename: str) -> str:
    return f"moments/{instance.couple_id}/{instance.moment_id}/original/{instance.id}-{filename}"


def moment_thumbnail_upload_path(instance, filename: str) -> str:
    return f"moments/{instance.couple_id}/{instance.moment_id}/thumbs/{instance.id}-{filename}"


class Moment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="moments")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_moments")
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    occurred_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "status", "created_at"]),
            models.Index(fields=["occurred_on", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.title}"


class MomentMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moment = models.ForeignKey(Moment, on_delete=models.CASCADE, related_name="media")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="moment_media")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_moment_media")
    media_type = models.CharField(max_length=20, choices=MediaType.choices, default=MediaType.IMAGE)
    file = models.ImageField(upload_to=moment_media_upload_path, max_length=500)
    thumbnail = models.ImageField(upload_to=moment_thumbnail_upload_path, max_length=500, blank=True)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=80)
    byte_size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    thumbnail_width = models.PositiveIntegerField(default=0)
    thumbnail_height = models.PositiveIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64)
    metadata_removed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["moment", "created_at"]),
            models.Index(fields=["couple", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.moment_id}:{self.filename}"


class MomentTopicLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moment = models.ForeignKey(Moment, on_delete=models.CASCADE, related_name="topic_links")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="moment_topic_links")
    topic = models.ForeignKey("topics.Topic", null=True, blank=True, on_delete=models.CASCADE, related_name="moment_links")
    custom_topic = models.ForeignKey("topics.CoupleTopic", null=True, blank=True, on_delete=models.CASCADE, related_name="moment_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["moment", "topic"], name="unique_moment_builtin_topic_link"),
            models.UniqueConstraint(fields=["moment", "custom_topic"], name="unique_moment_custom_topic_link"),
        ]
        indexes = [
            models.Index(fields=["moment", "created_at"]),
            models.Index(fields=["couple", "created_at"]),
        ]


class MomentMediaDownloadToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media = models.ForeignKey(MomentMedia, on_delete=models.CASCADE, related_name="download_tokens")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="moment_media_tokens")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="moment_media_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    variant = models.CharField(max_length=20, default="original")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"]),
            models.Index(fields=["couple", "expires_at"]),
        ]
