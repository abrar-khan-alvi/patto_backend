from django.urls import path

from apps.couples.views import (
    CoupleCreateView,
    CurrentCoupleView,
    PartnerInvitationAcceptView,
    PartnerInvitationCreateView,
    PartnerInvitationRevokeView,
)

urlpatterns = [
    path("couples/", CoupleCreateView.as_view(), name="couple-create"),
    path("couples/current/", CurrentCoupleView.as_view(), name="couple-current"),
    path("couples/<uuid:couple_id>/invitations/", PartnerInvitationCreateView.as_view(), name="partner-invitation-create"),
    path("couples/invitations/accept/", PartnerInvitationAcceptView.as_view(), name="partner-invitation-accept"),
    path("couples/invitations/<uuid:invitation_id>/revoke/", PartnerInvitationRevokeView.as_view(), name="partner-invitation-revoke"),
]
