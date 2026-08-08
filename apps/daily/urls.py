from django.urls import path

from apps.daily.views import CurrentDailyAssignmentView, DailyAnswerSubmitView, DailyAssignmentDetailView

urlpatterns = [
    path("daily/current/", CurrentDailyAssignmentView.as_view(), name="daily-current"),
    path("daily/<uuid:assignment_id>/", DailyAssignmentDetailView.as_view(), name="daily-detail"),
    path("daily/<uuid:assignment_id>/answers/", DailyAnswerSubmitView.as_view(), name="daily-answer-submit"),
]
