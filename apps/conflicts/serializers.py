from rest_framework import serializers

from apps.conflicts.models import ConflictBridge, ConflictMessage, ConflictMediation, ConflictPerspective, ConflictResolution, ConflictThread


class ConflictPerspectiveSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ConflictPerspective
        fields = ["id", "user_id", "user_email", "situation", "feelings", "needs", "requested_outcome", "locked_at", "created_at"]


class ConflictBridgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConflictBridge
        fields = ["id", "status", "model", "neutral_summary", "partner_summaries", "common_ground", "next_steps", "safety_flags", "error_code", "error_message", "created_at"]


class ConflictMessageSerializer(serializers.ModelSerializer):
    author_id = serializers.UUIDField(source="author.id", read_only=True)
    author_email = serializers.EmailField(source="author.email", read_only=True)

    class Meta:
        model = ConflictMessage
        fields = ["id", "sender_type", "author_id", "author_email", "body", "render_as", "metadata", "created_at"]


class ConflictMediationSerializer(serializers.ModelSerializer):
    requested_by_id = serializers.UUIDField(source="requested_by.id", read_only=True)

    class Meta:
        model = ConflictMediation
        fields = ["id", "requested_by_id", "status", "prompt", "response", "created_at"]


class ConflictResolutionSerializer(serializers.ModelSerializer):
    resolved_by_id = serializers.UUIDField(source="resolved_by.id", read_only=True)

    class Meta:
        model = ConflictResolution
        fields = ["id", "resolved_by_id", "summary", "proposed_pact_changes", "created_at"]


class ConflictThreadSerializer(serializers.ModelSerializer):
    perspectives = serializers.SerializerMethodField()
    bridge = ConflictBridgeSerializer(read_only=True)
    messages = ConflictMessageSerializer(many=True, read_only=True)
    mediations = ConflictMediationSerializer(many=True, read_only=True)
    resolution = ConflictResolutionSerializer(read_only=True)

    class Meta:
        model = ConflictThread
        fields = ["id", "title", "status", "created_by", "resolved_at", "perspectives", "bridge", "messages", "mediations", "resolution", "created_at", "updated_at"]

    def get_perspectives(self, obj):
        user = self.context.get("user")
        if user is None:
            return []
        return ConflictPerspectiveSerializer(obj.perspectives.filter(user=user), many=True).data


class ConflictThreadCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)


class ConflictPerspectiveSubmitSerializer(serializers.Serializer):
    situation = serializers.CharField(max_length=5000, trim_whitespace=True)
    feelings = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    needs = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    requested_outcome = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    lock = serializers.BooleanField(required=False, default=False)


class ConflictMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class ConflictMediationCreateSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True, max_length=3000)


class ConflictResolutionCreateSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=5000, trim_whitespace=True)
    proposed_pact_changes = serializers.ListField(child=serializers.CharField(max_length=1000), required=False, allow_empty=True)
