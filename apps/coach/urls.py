from django.urls import path

from apps.coach.views import CoachConversationDetailView, CoachConversationListView, CoachMessageCreateView, CoachMessageShareView, CoachRunCreateView

urlpatterns = [
    path("coach/conversations/", CoachConversationListView.as_view(), name="coach-conversation-list"),
    path("coach/conversations/<uuid:conversation_id>/", CoachConversationDetailView.as_view(), name="coach-conversation-detail"),
    path("coach/conversations/<uuid:conversation_id>/messages/", CoachMessageCreateView.as_view(), name="coach-message-create"),
    path("coach/conversations/<uuid:conversation_id>/run/", CoachRunCreateView.as_view(), name="coach-run-create"),
    path("coach/messages/<uuid:message_id>/share/", CoachMessageShareView.as_view(), name="coach-message-share"),
]
