from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.couples.services import user_active_membership
from apps.insights.models import MonthlyInsight
from apps.insights.serializers import MonthlyInsightRunSerializer, MonthlyInsightSerializer
from apps.insights.services import MonthlyInsightNotClosed, get_or_create_monthly_insight_job
from apps.insights.tasks import run_monthly_insight_task


class MonthlyInsightListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response({"results": []})
        insights = MonthlyInsight.objects.filter(couple=membership.couple).select_related("prompt_version").order_by("-year", "-month")
        return Response({"results": MonthlyInsightSerializer(insights, many=True).data})

    def post(self, request):
        membership = user_active_membership(request.user)
        if membership is None:
            return Response(
                {"error": {"code": "no_active_couple", "message": "Join an active couple before running monthly insights."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MonthlyInsightRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            insight = get_or_create_monthly_insight_job(
                couple=membership.couple,
                user=request.user,
                year=serializer.validated_data["year"],
                month=serializer.validated_data["month"],
            )
        except MonthlyInsightNotClosed:
            return Response(
                {"error": {"code": "month_not_closed", "message": "Monthly insights can only run after the target month closes."}},
                status=status.HTTP_409_CONFLICT,
            )
        if insight.status == MonthlyInsight.Status.QUEUED and settings.AI_AUTO_DISPATCH_MONTHLY_INSIGHTS:
            run_monthly_insight_task.delay(str(insight.id))
        return Response(MonthlyInsightSerializer(insight).data, status=status.HTTP_202_ACCEPTED)
