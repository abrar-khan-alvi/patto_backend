from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.services import user_active_membership
from apps.discussions.models import DiscussionThread
from apps.discussions.serializers import (
    DiscussionMessageCreateSerializer,
    DiscussionMessageSerializer,
    DiscussionThreadCreateSerializer,
    DiscussionThreadListSerializer,
    DiscussionThreadSerializer,
    MediationRequestSerializer,
)
from apps.discussions.services import create_discussion_message, create_discussion_thread, request_mediation


class DiscussionThreadListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        threads = (
            DiscussionThread.objects.filter(couple=membership.couple)
            .prefetch_related("messages")
            .order_by("-updated_at")
        )
        return Response({"results": DiscussionThreadListSerializer(threads, many=True).data})

    def post(self, request):
        serializer = DiscussionThreadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            thread = create_discussion_thread(
                user=request.user,
                session_id=serializer.validated_data.get("session_id"),
                analysis_run_id=serializer.validated_data.get("analysis_run_id"),
                title=serializer.validated_data.get("title", ""),
                request_id=getattr(request, "request_id", ""),
            )
        except ObjectDoesNotExist:
            return Response({"error": {"code": "not_found", "message": "Discussion target was not found."}}, status=404)
        return Response(DiscussionThreadSerializer(thread).data, status=status.HTTP_201_CREATED)


class DiscussionThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_thread(self, request, thread_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return None
        return get_object_or_404(
            DiscussionThread.objects.prefetch_related("messages", "mediation_requests"),
            id=thread_id,
            couple=membership.couple,
        )

    def get(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if thread is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(DiscussionThreadSerializer(thread).data)


class DiscussionMessageCreateView(DiscussionThreadDetailView):
    def post(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if thread is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = DiscussionMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = create_discussion_message(
            thread=thread,
            user=request.user,
            body=serializer.validated_data["body"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(DiscussionMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class MediationRequestCreateView(DiscussionThreadDetailView):
    def post(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if thread is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mediation_request = request_mediation(
            thread=thread,
            user=request.user,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(MediationRequestSerializer(mediation_request).data, status=status.HTTP_201_CREATED)
