from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.challenges.models import Challenge, ChallengeAssignment
from apps.challenges.serializers import (
    ChallengeAssignmentCreateSerializer,
    ChallengeAssignmentSerializer,
    ChallengeCompletionSerializer,
    ChallengeSerializer,
)
from apps.challenges.services import assign_curated_challenge, complete_challenge_assignment
from apps.couples.services import user_active_membership


class ChallengeCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        challenges = Challenge.objects.filter(is_active=True).order_by("sort_order", "stable_key")
        return Response({"results": ChallengeSerializer(challenges, many=True).data})


class ChallengeAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        assignments = (
            ChallengeAssignment.objects.filter(couple=membership.couple)
            .select_related("challenge")
            .prefetch_related("member_completions", "member_completions__user")
            .order_by("-created_at")
        )
        return Response({"results": ChallengeAssignmentSerializer(assignments, many=True).data})

    def post(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Join an active couple before assigning challenges."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ChallengeAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = get_object_or_404(Challenge, id=serializer.validated_data["challenge_id"])
        assignment = assign_curated_challenge(
            couple=membership.couple,
            user=request.user,
            challenge=challenge,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(ChallengeAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class ChallengeAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assignment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        assignment = get_object_or_404(
            ChallengeAssignment.objects.select_related("challenge").prefetch_related("member_completions", "member_completions__user"),
            id=assignment_id,
            couple=membership.couple,
        )
        return Response(ChallengeAssignmentSerializer(assignment).data)


class ChallengeAssignmentCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        assignment = get_object_or_404(ChallengeAssignment.objects.select_related("couple", "challenge"), id=assignment_id, couple=membership.couple)
        serializer = ChallengeCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complete_challenge_assignment(
            assignment=assignment,
            user=request.user,
            note=serializer.validated_data.get("note", ""),
            request_id=getattr(request, "request_id", ""),
        )
        assignment.refresh_from_db()
        return Response(ChallengeAssignmentSerializer(assignment).data)
