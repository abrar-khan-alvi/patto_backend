from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import AnalysisRun
from apps.analysis.serializers import AnalysisRunSerializer
from apps.couples.services import user_active_membership
from apps.responses.models import TopicSession


class TopicSessionAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        session = get_object_or_404(TopicSession.objects.select_related("couple"), id=session_id, couple=membership.couple)
        run = (
            AnalysisRun.objects.filter(session=session)
            .select_related("topic_analysis")
            .prefetch_related("alignment_dimensions", "conversation_starters", "proposed_clauses")
            .order_by("-version")
            .first()
        )
        if run is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(AnalysisRunSerializer(run).data)
