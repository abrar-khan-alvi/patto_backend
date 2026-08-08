from django.urls import path

from apps.insights.views import MonthlyInsightListView

urlpatterns = [
    path("monthly-insights/", MonthlyInsightListView.as_view(), name="monthly-insights"),
]
