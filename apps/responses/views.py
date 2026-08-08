from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.serializers import AIFollowUpQuestionSerializer
from apps.ai.services import generate_follow_up_question
from apps.couples.services import user_active_membership
from apps.responses.models import TopicSession
from apps.responses.serializers import (
    TopicAnswersSubmitSerializer,
    TopicResponseSerializer,
    TopicSessionCreateSerializer,
    TopicSessionSerializer,
)
from apps.responses.services import (
    complete_topic_session,
    get_or_create_topic_session,
    save_topic_answers,
    session_is_released,
    sync_state_for_user,
    visible_responses_for_user,
)


class TopicSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Join an active couple before answering topics."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TopicSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = get_or_create_topic_session(
            couple=membership.couple,
            user=request.user,
            topic_kind=serializer.validated_data["topic_kind"],
            topic_id=serializer.validated_data["topic_id"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(TopicSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class TopicSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_session(self, request, session_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return None
        return get_object_or_404(TopicSession.objects.select_related("couple"), id=session_id, couple=membership.couple)

    def get(self, request, session_id):
        session = self.get_session(request, session_id)
        if session is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        responses = visible_responses_for_user(session=session, user=request.user)
        completion_user_ids = set(str(item.user_id) for item in session.completions.all())
        return Response(
            {
                "session": TopicSessionSerializer(session).data,
                "is_released": session_is_released(session),
                "completed_user_ids": sorted(completion_user_ids),
                "sync": sync_state_for_user(session=session, user=request.user),
                "responses": TopicResponseSerializer(responses, many=True).data,
            }
        )


class TopicAnswerSaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(TopicSession.objects.select_related("couple"), id=session_id)
        serializer = TopicAnswersSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = save_topic_answers(
            session=session,
            user=request.user,
            answers=serializer.validated_data["answers"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response({"responses": TopicResponseSerializer(answers, many=True).data})


class TopicCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(TopicSession.objects.select_related("couple"), id=session_id)
        serializer = TopicAnswersSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complete_topic_session(
            session=session,
            user=request.user,
            answers=serializer.validated_data["answers"],
            request_id=getattr(request, "request_id", ""),
        )
        session.refresh_from_db()
        responses = visible_responses_for_user(session=session, user=request.user)
        return Response(
            {
                "session": TopicSessionSerializer(session).data,
                "is_released": session_is_released(session),
                "sync": sync_state_for_user(session=session, user=request.user),
                "responses": TopicResponseSerializer(responses, many=True).data,
            }
        )


class TopicFollowUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        session = get_object_or_404(TopicSession.objects.select_related("couple"), id=session_id, couple=membership.couple)
        follow_up = generate_follow_up_question(
            session=session,
            user=request.user,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(AIFollowUpQuestionSerializer(follow_up).data)
