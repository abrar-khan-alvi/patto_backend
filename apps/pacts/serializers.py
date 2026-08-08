from rest_framework import serializers

from apps.pacts.models import ClauseApproval, ClauseProposal, Pact, PactClause, PactDocument, PactSection, PactVersion


class PactCreateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=180)
    proposed_clause_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    manual_clauses = serializers.ListField(child=serializers.CharField(max_length=3000), required=False)


class ClauseProposalEditSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=3000)


class ClauseApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClauseApproval
        fields = ["id", "user", "role", "proposal_revision", "approved_at", "invalidated_at"]


class ClauseProposalSerializer(serializers.ModelSerializer):
    approvals = ClauseApprovalSerializer(many=True, read_only=True)

    class Meta:
        model = ClauseProposal
        fields = ["id", "source_proposed_clause", "text", "revision", "approvals", "created_at", "updated_at"]


class PactClauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = PactClause
        fields = ["id", "text", "source_proposed_clause", "sort_order", "created_at"]


class PactSectionSerializer(serializers.ModelSerializer):
    clauses = PactClauseSerializer(many=True, read_only=True)

    class Meta:
        model = PactSection
        fields = ["id", "title", "sort_order", "clauses", "created_at"]


class PactVersionSerializer(serializers.ModelSerializer):
    clause_proposals = ClauseProposalSerializer(many=True, read_only=True)
    sections = PactSectionSerializer(many=True, read_only=True)

    class Meta:
        model = PactVersion
        fields = [
            "id",
            "version",
            "status",
            "based_on_version",
            "proposed_by",
            "proposed_at",
            "activated_at",
            "clause_proposals",
            "sections",
            "created_at",
            "updated_at",
        ]


class PactSerializer(serializers.ModelSerializer):
    versions = PactVersionSerializer(many=True, read_only=True)
    live_version_id = serializers.UUIDField(source="live_version.id", read_only=True)

    class Meta:
        model = Pact
        fields = ["id", "title", "live_version_id", "created_by", "versions", "created_at", "updated_at"]


class PactListSerializer(serializers.ModelSerializer):
    live_version_id = serializers.UUIDField(source="live_version.id", read_only=True)

    class Meta:
        model = Pact
        fields = ["id", "title", "live_version_id", "created_at", "updated_at"]


class PactDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PactDocument
        fields = ["id", "version", "filename", "checksum_sha256", "byte_size", "generated_at", "emailed_at", "email_attempts"]


class PactDocumentDownloadLinkSerializer(serializers.Serializer):
    document = PactDocumentSerializer(read_only=True)
    token = serializers.CharField(read_only=True)
    download_url = serializers.CharField(read_only=True)
    expires_in_minutes = serializers.IntegerField(read_only=True)
