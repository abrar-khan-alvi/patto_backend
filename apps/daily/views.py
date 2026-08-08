from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.services import user_active_membership
from apps.daily.models import DailyAssignment
from apps.daily.serializers import DailyAnswerSerializer, DailyAnswerSubmitSerializer, DailyAssignmentSerializer
from apps.daily.services import (
    DailyAccessDenied,
    DailyAlreadyRevealed,
    DailyQuestionUnavailable,
    get_or_create_daily_assignment,
    submit_daily_answer,
    visible_daily_answers_for_user,
)


def daily_assignment_response(*, assignment, user):
    return {
        "assignment": DailyAssignmentSerializer(assignment).data,
        "answers": DailyAnswerSerializer(visible_daily_answers_for_user(assignment=assignment, user=user), many=True).data,
    }


class CurrentDailyAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Join an active couple before answering daily questions."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            assignment = get_or_create_daily_assignment(couple=membership.couple, user=request.user)
        except DailyQuestionUnavailable:
            return Response(
                {"error": {"code": "daily_catalog_empty", "message": "No active daily questions are configured."}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(daily_assignment_response(assignment=assignment, user=request.user))


class DailyAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assignment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        assignment = get_object_or_404(
            DailyAssignment.objects.select_related("couple", "question"),
            id=assignment_id,
            couple=membership.couple,
        )
        return Response(daily_assignment_response(assignment=assignment, user=request.user))


class DailyAnswerSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        assignment = get_object_or_404(
            DailyAssignment.objects.select_related("couple", "question"),
            id=assignment_id,
            couple=membership.couple,
        )
        serializer = DailyAnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submit_daily_answer(
                assignment=assignment,
                user=request.user,
                text_answer=serializer.validated_data["text_answer"],
            )
        except DailyAccessDenied:
            return Response(status=status.HTTP_403_FORBIDDEN)
        except DailyAlreadyRevealed:
            return Response(
                {"error": {"code": "daily_revealed", "message": "Daily answers are locked after reveal."}},
                status=status.HTTP_409_CONFLICT,
            )
        assignment.refresh_from_db()
        return Response(daily_assignment_response(assignment=assignment, user=request.user))
