from django.urls import path

from apps.profile_features.views import (
    AccountDeletionRequestView,
    DataExportRequestView,
    ReferralApplyView,
    ReferralCodeView,
    ReferralListView,
    SubscriptionManagementView,
    SupportTicketListView,
    SupportTicketMessageView,
)

urlpatterns = [
    path("referrals/code/", ReferralCodeView.as_view(), name="referral-code"),
    path("referrals/apply/", ReferralApplyView.as_view(), name="referral-apply"),
    path("referrals/", ReferralListView.as_view(), name="referral-list"),
    path("support-tickets/", SupportTicketListView.as_view(), name="support-ticket-list"),
    path("support-tickets/<uuid:ticket_id>/messages/", SupportTicketMessageView.as_view(), name="support-ticket-message"),
    path("subscription-management/", SubscriptionManagementView.as_view(), name="subscription-management"),
    path("data-export-requests/", DataExportRequestView.as_view(), name="data-export-requests"),
    path("account-deletion-requests/", AccountDeletionRequestView.as_view(), name="account-deletion-requests"),
]
