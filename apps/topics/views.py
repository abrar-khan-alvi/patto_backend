from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.topics.models import Question, Topic
from apps.couples.services import user_active_membership
from apps.topics.models import CoupleTopic
from apps.topics.serializers import (
    CoupleTopicSerializer,
    CoupleTopicWriteSerializer,
    TopicDetailSerializer,
    TopicListSerializer,
)
from apps.topics.services import create_custom_topic, deactivate_custom_topic, update_custom_topic


class TopicListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TopicListSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Topic.objects.filter(is_active=True)
            .prefetch_related("translations", "questions")
            .annotate(active_question_count=Count("questions", filter=Q(questions__is_active=True)))
            .order_by("sort_order", "slug")
        )


class TopicDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TopicDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Topic.objects.filter(is_active=True)
            .prefetch_related(
                "translations",
                Prefetch(
                    "questions",
                    queryset=Question.objects.filter(is_active=True).prefetch_related(
                        "translations",
                        "options__translations",
                    ),
                ),
            )
            .order_by("sort_order", "slug")
        )


class CustomTopicListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"custom_topics": []})
        topics = CoupleTopic.objects.filter(couple=membership.couple, is_active=True).prefetch_related("questions__options")
        return Response({"custom_topics": CoupleTopicSerializer(topics, many=True).data})

    def post(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Create or join a couple before adding custom topics."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CoupleTopicWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = create_custom_topic(
            couple=membership.couple,
            created_by=request.user,
            data=serializer.validated_data,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(CoupleTopicSerializer(topic).data, status=status.HTTP_201_CREATED)


class CustomTopicDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_topic(self, request, topic_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return None
        return get_object_or_404(
            CoupleTopic.objects.prefetch_related("questions__options"),
            id=topic_id,
            couple=membership.couple,
        )

    def get(self, request, topic_id):
        topic = self.get_topic(request, topic_id)
        if topic is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(CoupleTopicSerializer(topic).data)

    def put(self, request, topic_id):
        topic = self.get_topic(request, topic_id)
        if topic is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = CoupleTopicWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_topic = update_custom_topic(
            topic=topic,
            updated_by=request.user,
            data=serializer.validated_data,
            request_id=getattr(request, "request_id", ""),
        )
        return Response(CoupleTopicSerializer(updated_topic).data)

    def delete(self, request, topic_id):
        topic = self.get_topic(request, topic_id)
        if topic is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deactivate_custom_topic(topic=topic, deleted_by=request.user, request_id=getattr(request, "request_id", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)
