from django.urls import path

from apps.analysis.views import TopicSessionAnalysisView
from apps.responses.views import (
    TopicAnswerSaveView,
    TopicCompleteView,
    TopicFollowUpView,
    TopicSessionCreateView,
    TopicSessionDetailView,
)

urlpatterns = [
    path("topic-sessions/", TopicSessionCreateView.as_view(), name="topic-session-create"),
    path("topic-sessions/<uuid:session_id>/", TopicSessionDetailView.as_view(), name="topic-session-detail"),
    path("topic-sessions/<uuid:session_id>/answers/", TopicAnswerSaveView.as_view(), name="topic-answer-save"),
    path("topic-sessions/<uuid:session_id>/complete/", TopicCompleteView.as_view(), name="topic-complete"),
    path("topic-sessions/<uuid:session_id>/follow-up/", TopicFollowUpView.as_view(), name="topic-follow-up"),
    path("topic-sessions/<uuid:session_id>/analysis/", TopicSessionAnalysisView.as_view(), name="topic-session-analysis"),
]
