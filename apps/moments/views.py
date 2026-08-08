from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.services import user_active_membership
from apps.moments.models import Moment, MomentMedia
from apps.moments.serializers import MomentCreateSerializer, MomentMediaLinkSerializer, MomentMediaSerializer, MomentMediaUploadSerializer, MomentSerializer
from apps.moments.services import (
    create_moment,
    create_moment_media_download_token,
    moment_media_file_response,
    resolve_moment_media_download,
    upload_moment_media,
)


class MomentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        moments = (
            Moment.objects.filter(couple=membership.couple)
            .prefetch_related("media", "topic_links", "topic_links__topic", "topic_links__custom_topic")
            .order_by("-occurred_on", "-created_at")
        )
        return Response({"results": MomentSerializer(moments, many=True).data})

    def post(self, request):
        serializer = MomentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        moment = create_moment(
            user=request.user,
            title=serializer.validated_data["title"],
            body=serializer.validated_data.get("body", ""),
            occurred_on=serializer.validated_data.get("occurred_on"),
            topic_ids=serializer.validated_data.get("topic_ids", []),
            custom_topic_ids=serializer.validated_data.get("custom_topic_ids", []),
            request_id=getattr(request, "request_id", ""),
        )
        return Response(MomentSerializer(moment).data, status=status.HTTP_201_CREATED)


class MomentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, moment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        moment = get_object_or_404(
            Moment.objects.prefetch_related("media", "topic_links", "topic_links__topic", "topic_links__custom_topic"),
            id=moment_id,
            couple=membership.couple,
        )
        return Response(MomentSerializer(moment).data)


class MomentMediaUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, moment_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        moment = get_object_or_404(Moment.objects.select_related("couple"), id=moment_id, couple=membership.couple)
        serializer = MomentMediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = upload_moment_media(
            moment=moment,
            user=request.user,
            uploaded_file=serializer.validated_data["file"],
            request_id=getattr(request, "request_id", ""),
        )
        return Response(MomentMediaSerializer(media).data, status=status.HTTP_201_CREATED)


class MomentMediaLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, media_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        media = get_object_or_404(MomentMedia.objects.select_related("couple", "moment"), id=media_id, couple=membership.couple)
        serializer = MomentMediaLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, download_url = create_moment_media_download_token(
            media=media,
            user=request.user,
            variant=serializer.validated_data["variant"],
        )
        return Response({"token": token, "download_url": download_url, "variant": serializer.validated_data["variant"]})


class MomentMediaDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        download_token = resolve_moment_media_download(token=token, user=request.user)
        return moment_media_file_response(download_token=download_token)
