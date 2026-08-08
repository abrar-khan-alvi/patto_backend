from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.conflicts.models import ConflictThread
from apps.conflicts.serializers import (
    ConflictBridgeSerializer,
    ConflictMessageCreateSerializer,
    ConflictMessageSerializer,
    ConflictMediationCreateSerializer,
    ConflictMediationSerializer,
    ConflictPerspectiveSerializer,
    ConflictPerspectiveSubmitSerializer,
    ConflictResolutionCreateSerializer,
    ConflictResolutionSerializer,
    ConflictThreadCreateSerializer,
    ConflictThreadSerializer,
)
from apps.conflicts.services import (
    add_conflict_message,
    create_conflict_thread,
    ensure_conflict_member,
    request_conflict_mediation,
    resolve_conflict,
    run_conflict_bridge,
    submit_conflict_perspective,
)
from apps.couples.services import user_active_membership


def serialize_thread(thread, user):
    return ConflictThreadSerializer(thread, context={"user": user}).data


class ConflictThreadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        threads = (
            ConflictThread.objects.filter(couple=membership.couple)
            .select_related("created_by")
            .prefetch_related("perspectives", "messages", "mediations")
            .order_by("-created_at")
        )
        return Response({"results": ConflictThreadSerializer(threads, many=True, context={"user": request.user}).data})

    def post(self, request):
        serializer = ConflictThreadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        thread = create_conflict_thread(user=request.user, title=serializer.validated_data["title"], request_id=getattr(request, "request_id", ""))
        return Response(serialize_thread(thread, request.user), status=status.HTTP_201_CREATED)


class ConflictThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple", "created_by").prefetch_related("perspectives", "messages", "mediations"), id=thread_id)
        ensure_conflict_member(user=request.user, thread=thread)
        return Response(serialize_thread(thread, request.user))


class ConflictPerspectiveSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple"), id=thread_id)
        serializer = ConflictPerspectiveSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perspective = submit_conflict_perspective(
            thread=thread,
            user=request.user,
            situation=serializer.validated_data["situation"],
            feelings=serializer.validated_data.get("feelings", ""),
            needs=serializer.validated_data.get("needs", ""),
            requested_outcome=serializer.validated_data.get("requested_outcome", ""),
            lock=serializer.validated_data.get("lock", False),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(ConflictPerspectiveSerializer(perspective).data)


class ConflictBridgeRunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple"), id=thread_id)
        bridge = run_conflict_bridge(thread=thread, user=request.user, request_id=getattr(request, "request_id", ""))
        return Response(ConflictBridgeSerializer(bridge).data, status=status.HTTP_201_CREATED)


class ConflictMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple"), id=thread_id)
        serializer = ConflictMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = add_conflict_message(thread=thread, user=request.user, body=serializer.validated_data["body"], request_id=getattr(request, "request_id", ""))
        return Response(ConflictMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class ConflictMediationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple"), id=thread_id)
        serializer = ConflictMediationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mediation = request_conflict_mediation(thread=thread, user=request.user, prompt=serializer.validated_data.get("prompt", ""), request_id=getattr(request, "request_id", ""))
        return Response(ConflictMediationSerializer(mediation).data, status=status.HTTP_201_CREATED)


class ConflictResolutionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        thread = get_object_or_404(ConflictThread.objects.select_related("couple"), id=thread_id)
        serializer = ConflictResolutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolution = resolve_conflict(
            thread=thread,
            user=request.user,
            summary=serializer.validated_data["summary"],
            proposed_pact_changes=serializer.validated_data.get("proposed_pact_changes", []),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(ConflictResolutionSerializer(resolution).data, status=status.HTTP_201_CREATED)
