from django.urls import path

from apps.challenges.views import ChallengeAssignmentCompletionView, ChallengeAssignmentDetailView, ChallengeAssignmentListView, ChallengeCatalogView

urlpatterns = [
    path("challenges/", ChallengeCatalogView.as_view(), name="challenge-catalog"),
    path("challenge-assignments/", ChallengeAssignmentListView.as_view(), name="challenge-assignment-list"),
    path("challenge-assignments/<uuid:assignment_id>/", ChallengeAssignmentDetailView.as_view(), name="challenge-assignment-detail"),
    path("challenge-assignments/<uuid:assignment_id>/complete/", ChallengeAssignmentCompletionView.as_view(), name="challenge-assignment-complete"),
]
