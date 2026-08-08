from django.urls import path

from apps.topics.views import CustomTopicDetailView, CustomTopicListCreateView, TopicDetailView, TopicListView

urlpatterns = [
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<slug:slug>/", TopicDetailView.as_view(), name="topic-detail"),
    path("custom-topics/", CustomTopicListCreateView.as_view(), name="custom-topic-list-create"),
    path("custom-topics/<uuid:topic_id>/", CustomTopicDetailView.as_view(), name="custom-topic-detail"),
]
