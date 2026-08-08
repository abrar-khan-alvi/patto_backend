from django.urls import path

from apps.discussions.views import (
    DiscussionMessageCreateView,
    DiscussionThreadDetailView,
    DiscussionThreadListCreateView,
    MediationRequestCreateView,
)

urlpatterns = [
    path("discussion-threads/", DiscussionThreadListCreateView.as_view(), name="discussion-thread-list-create"),
    path("discussion-threads/<uuid:thread_id>/", DiscussionThreadDetailView.as_view(), name="discussion-thread-detail"),
    path("discussion-threads/<uuid:thread_id>/messages/", DiscussionMessageCreateView.as_view(), name="discussion-message-create"),
    path("discussion-threads/<uuid:thread_id>/mediation-requests/", MediationRequestCreateView.as_view(), name="mediation-request-create"),
]
