from django.urls import path

from apps.conflicts.views import (
    ConflictBridgeRunView,
    ConflictMessageCreateView,
    ConflictMediationCreateView,
    ConflictPerspectiveSubmitView,
    ConflictResolutionCreateView,
    ConflictThreadDetailView,
    ConflictThreadListView,
)

urlpatterns = [
    path("conflicts/", ConflictThreadListView.as_view(), name="conflict-list"),
    path("conflicts/<uuid:thread_id>/", ConflictThreadDetailView.as_view(), name="conflict-detail"),
    path("conflicts/<uuid:thread_id>/perspective/", ConflictPerspectiveSubmitView.as_view(), name="conflict-perspective-submit"),
    path("conflicts/<uuid:thread_id>/bridge/", ConflictBridgeRunView.as_view(), name="conflict-bridge-run"),
    path("conflicts/<uuid:thread_id>/messages/", ConflictMessageCreateView.as_view(), name="conflict-message-create"),
    path("conflicts/<uuid:thread_id>/mediations/", ConflictMediationCreateView.as_view(), name="conflict-mediation-create"),
    path("conflicts/<uuid:thread_id>/resolve/", ConflictResolutionCreateView.as_view(), name="conflict-resolve"),
]
