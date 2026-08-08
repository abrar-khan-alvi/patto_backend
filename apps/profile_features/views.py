from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profile_features.models import AccountDeletionRequest, DataExportRequest, Referral, SupportTicket
from apps.profile_features.serializers import (
    AccountDeletionRequestCreateSerializer,
    AccountDeletionRequestSerializer,
    DataExportRequestSerializer,
    ReferralApplySerializer,
    ReferralCodeSerializer,
    ReferralSerializer,
    SubscriptionManagementRequestCreateSerializer,
    SubscriptionManagementRequestSerializer,
    SupportTicketCreateSerializer,
    SupportTicketMessageCreateSerializer,
    SupportTicketMessageSerializer,
    SupportTicketSerializer,
)
from apps.profile_features.services import (
    add_support_ticket_message,
    apply_referral_code,
    create_account_deletion_request,
    create_data_export_request,
    create_subscription_management_request,
    create_support_ticket,
    current_subscription_management_payload,
    get_or_create_referral_code,
)
from apps.billing.serializers import SubscriptionSerializer


class ReferralCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ReferralCodeSerializer(get_or_create_referral_code(user=request.user)).data)


class ReferralApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReferralApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        referral = apply_referral_code(user=request.user, code=serializer.validated_data["code"], request_id=getattr(request, "request_id", ""))
        return Response(ReferralSerializer(referral).data, status=status.HTTP_201_CREATED)


class ReferralListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sent = Referral.objects.filter(referrer=request.user).select_related("referrer", "referred_user").order_by("-created_at")
        received = Referral.objects.filter(referred_user=request.user).select_related("referrer", "referred_user").order_by("-created_at")
        return Response({"sent": ReferralSerializer(sent, many=True).data, "received": ReferralSerializer(received, many=True).data})


class SupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = SupportTicket.objects.filter(user=request.user).prefetch_related("messages").order_by("-created_at")
        return Response({"results": SupportTicketSerializer(tickets, many=True).data})

    def post(self, request):
        serializer = SupportTicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = create_support_ticket(
            user=request.user,
            category=serializer.validated_data["category"],
            subject=serializer.validated_data["subject"],
            body=serializer.validated_data["body"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class SupportTicketMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
        serializer = SupportTicketMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = add_support_ticket_message(ticket=ticket, user=request.user, body=serializer.validated_data["body"], request_id=getattr(request, "request_id", ""))
        return Response(SupportTicketMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class SubscriptionManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = current_subscription_management_payload(user=request.user)
        return Response(
            {
                "current_subscription": SubscriptionSerializer(payload["current_subscription"]).data if payload["current_subscription"] else None,
                "platform_management": payload["platform_management"],
            }
        )

    def post(self, request):
        serializer = SubscriptionManagementRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = create_subscription_management_request(
            user=request.user,
            request_type=serializer.validated_data["request_type"],
            platform=serializer.validated_data.get("platform", ""),
            notes=serializer.validated_data.get("notes", ""),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(SubscriptionManagementRequestSerializer(request_obj).data, status=status.HTTP_201_CREATED)


class DataExportRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requests = DataExportRequest.objects.filter(user=request.user).order_by("-requested_at")
        return Response({"results": DataExportRequestSerializer(requests, many=True).data})

    def post(self, request):
        export_request = create_data_export_request(user=request.user, request_id=getattr(request, "request_id", ""))
        return Response(DataExportRequestSerializer(export_request).data, status=status.HTTP_201_CREATED)


class AccountDeletionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requests = AccountDeletionRequest.objects.filter(user=request.user).order_by("-requested_at")
        return Response({"results": AccountDeletionRequestSerializer(requests, many=True).data})

    def post(self, request):
        serializer = AccountDeletionRequestCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        deletion_request = create_account_deletion_request(user=request.user, reason=serializer.validated_data.get("reason", ""), request_id=getattr(request, "request_id", ""))
        return Response(AccountDeletionRequestSerializer(deletion_request).data, status=status.HTTP_201_CREATED)
