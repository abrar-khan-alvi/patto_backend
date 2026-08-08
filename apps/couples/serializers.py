from rest_framework import serializers

from apps.couples.models import Couple, CoupleMember, PartnerInvitation


class CoupleMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    display_name = serializers.CharField(source="user.profile.display_name", read_only=True)

    class Meta:
        model = CoupleMember
        fields = ["id", "email", "display_name", "role", "status", "joined_at"]


class CoupleSerializer(serializers.ModelSerializer):
    members = CoupleMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Couple
        fields = ["id", "status", "activated_at", "created_at", "members"]


class PartnerInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerInvitation
        fields = ["id", "email", "expires_at", "accepted_at", "revoked_at", "created_at"]


class PartnerInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PartnerInvitationCreatedSerializer(serializers.Serializer):
    invitation = PartnerInvitationSerializer()
    token = serializers.CharField()
    invite_url = serializers.URLField()


class PartnerInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
