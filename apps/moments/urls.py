from django.urls import path

from apps.moments.views import MomentDetailView, MomentListView, MomentMediaDownloadView, MomentMediaLinkView, MomentMediaUploadView

urlpatterns = [
    path("moments/", MomentListView.as_view(), name="moment-list"),
    path("moments/<uuid:moment_id>/", MomentDetailView.as_view(), name="moment-detail"),
    path("moments/<uuid:moment_id>/media/", MomentMediaUploadView.as_view(), name="moment-media-upload"),
    path("moment-media/<uuid:media_id>/download-link/", MomentMediaLinkView.as_view(), name="moment-media-download-link"),
    path("moment-media/<str:token>/download/", MomentMediaDownloadView.as_view(), name="moment-media-download"),
]
