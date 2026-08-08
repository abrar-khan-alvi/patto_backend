from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.models import Couple, PartnerInvitation
from apps.couples.permissions import CanCreatePartnerInvitation, CanRevokePartnerInvitation
from apps.couples.serializers import (
    CoupleSerializer,
    PartnerInvitationAcceptSerializer,
    PartnerInvitationCreateSerializer,
    PartnerInvitationCreatedSerializer,
)
from apps.couples.services import (
    accept_partner_invitation,
    create_couple,
    create_partner_invitation,
    revoke_partner_invitation,
    user_active_membership,
)


class CoupleCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        couple = create_couple(creator=request.user, request_id=getattr(request, "request_id", ""))
        return Response(CoupleSerializer(couple).data, status=status.HTTP_201_CREATED)


class CurrentCoupleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"couple": None})
        couple = Couple.objects.prefetch_related("members__user__profile").get(id=membership.couple_id)
        return Response({"couple": CoupleSerializer(couple).data})


class PartnerInvitationCreateView(APIView):
    permission_classes = [IsAuthenticated, CanCreatePartnerInvitation]

    def post(self, request, couple_id):
        serializer = PartnerInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        couple = get_object_or_404(Couple, id=couple_id)
        self.check_object_permissions(request, couple)
        result = create_partner_invitation(
            couple=couple,
            invited_by=request.user,
            email=serializer.validated_data["email"],
            request_id=getattr(request, "request_id", ""),
        )
        response_serializer = PartnerInvitationCreatedSerializer(
            {
                "invitation": result.invitation,
                "token": result.token,
                "invite_url": result.invite_url,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class PartnerInvitationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PartnerInvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        couple = accept_partner_invitation(
            token=serializer.validated_data["token"],
            accepted_by=request.user,
            request_id=getattr(request, "request_id", ""),
        )
        return Response({"couple": CoupleSerializer(couple).data})


class PartnerInvitationRevokeView(APIView):
    permission_classes = [IsAuthenticated, CanRevokePartnerInvitation]

    def post(self, request, invitation_id):
        invitation = get_object_or_404(PartnerInvitation.objects.select_related("couple"), id=invitation_id)
        self.check_object_permissions(request, invitation)
        revoke_partner_invitation(
            invitation=invitation,
            revoked_by=request.user,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
