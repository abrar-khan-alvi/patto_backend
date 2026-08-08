from rest_framework import serializers

from apps.moments.models import Moment, MomentMedia, MomentTopicLink


class MomentTopicLinkSerializer(serializers.ModelSerializer):
    topic_slug = serializers.CharField(source="topic.slug", read_only=True)
    custom_topic_title = serializers.CharField(source="custom_topic.title", read_only=True)

    class Meta:
        model = MomentTopicLink
        fields = ["id", "topic", "topic_slug", "custom_topic", "custom_topic_title", "created_at"]


class MomentMediaSerializer(serializers.ModelSerializer):
    uploaded_by_id = serializers.UUIDField(source="uploaded_by.id", read_only=True)

    class Meta:
        model = MomentMedia
        fields = [
            "id",
            "uploaded_by_id",
            "media_type",
            "filename",
            "content_type",
            "byte_size",
            "width",
            "height",
            "thumbnail_width",
            "thumbnail_height",
            "checksum_sha256",
            "metadata_removed",
            "created_at",
        ]


class MomentSerializer(serializers.ModelSerializer):
    media = MomentMediaSerializer(many=True, read_only=True)
    topic_links = MomentTopicLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Moment
        fields = [
            "id",
            "title",
            "body",
            "occurred_on",
            "status",
            "archived_at",
            "media",
            "topic_links",
            "created_at",
            "updated_at",
        ]


class MomentCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)
    body = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    occurred_on = serializers.DateField(required=False, allow_null=True)
    topic_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    custom_topic_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)


class MomentMediaUploadSerializer(serializers.Serializer):
    file = serializers.ImageField(required=True)


class MomentMediaLinkSerializer(serializers.Serializer):
    variant = serializers.ChoiceField(choices=["original", "thumbnail"], required=False, default="original")
