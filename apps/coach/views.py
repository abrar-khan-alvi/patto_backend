from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.coach.models import CoachConversation, CoachMessage
from apps.coach.serializers import (
    CoachConversationCreateSerializer,
    CoachConversationSerializer,
    CoachMessageCreateSerializer,
    CoachMessageSerializer,
    CoachRunSerializer,
)
from apps.coach.services import add_coach_message, create_coach_conversation, ensure_conversation_access, run_coach, share_individual_coach_message


class CoachConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = (
            CoachConversation.objects.filter(participants__user=request.user)
            .select_related("couple", "owner")
            .prefetch_related("participants", "participants__user", "messages", "messages__author")
            .distinct()
            .order_by("-created_at")
        )
        return Response({"results": CoachConversationSerializer(conversations, many=True).data})

    def post(self, request):
        serializer = CoachConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = create_coach_conversation(
            user=request.user,
            scope=serializer.validated_data["scope"],
            title=serializer.validated_data.get("title", ""),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(CoachConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


class CoachConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            CoachConversation.objects.select_related("couple", "owner").prefetch_related("participants", "participants__user", "messages", "messages__author"),
            id=conversation_id,
        )
        ensure_conversation_access(user=request.user, conversation=conversation)
        return Response(CoachConversationSerializer(conversation).data)


class CoachMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_object_or_404(CoachConversation.objects.select_related("couple", "owner"), id=conversation_id)
        serializer = CoachMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = add_coach_message(
            conversation=conversation,
            user=request.user,
            body=serializer.validated_data["body"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(CoachMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class CoachRunCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_object_or_404(CoachConversation.objects.select_related("couple", "owner"), id=conversation_id)
        run = run_coach(conversation=conversation, user=request.user, request_id=getattr(request, "request_id", ""))
        return Response(CoachRunSerializer(run).data, status=status.HTTP_201_CREATED)


class CoachMessageShareView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        message = get_object_or_404(CoachMessage.objects.select_related("conversation", "conversation__owner"), id=message_id)
        shared = share_individual_coach_message(message=message, user=request.user, request_id=getattr(request, "request_id", ""))
        return Response(CoachMessageSerializer(shared).data)
