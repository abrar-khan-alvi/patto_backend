from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.serializers import (
    DevelopmentIAPVerifySerializer,
    EntitlementSerializer,
    SubscriptionSerializer,
)
from apps.billing.services import verify_and_apply_development_iap
from apps.couples.models import Entitlement
from apps.couples.permissions import HasActiveEntitlement
from apps.couples.services import user_active_membership


class DevelopmentIAPVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Create a couple before attaching billing."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DevelopmentIAPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = verify_and_apply_development_iap(
            couple=membership.couple,
            owner=request.user,
            platform=serializer.validated_data["platform"],
            receipt_payload=serializer.validated_data["receipt"],
            request_id=getattr(request, "request_id", ""),
        )
        entitlement = Entitlement.objects.filter(
            couple=membership.couple,
            external_reference=subscription.original_transaction_id,
        ).first()
        return Response(
            {
                "subscription": SubscriptionSerializer(subscription).data,
                "entitlement": EntitlementSerializer(entitlement).data if entitlement else None,
            },
            status=status.HTTP_200_OK,
        )


class CurrentEntitlementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"entitlement": None, "has_active_entitlement": False})

        entitlements = Entitlement.objects.filter(couple=membership.couple).order_by("-updated_at")
        active_entitlement = next((entitlement for entitlement in entitlements if entitlement.is_active()), None)
        return Response(
            {
                "entitlement": EntitlementSerializer(active_entitlement).data if active_entitlement else None,
                "has_active_entitlement": HasActiveEntitlement().has_object_permission(
                    request,
                    self,
                    membership.couple,
                ),
            }
        )
