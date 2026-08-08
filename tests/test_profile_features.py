from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import AuthSession, User
from apps.billing.models import Subscription
from apps.couples.models import Couple, CoupleMember, Entitlement
from apps.notifications.models import Notification, NotificationPreference
from apps.profile_features.models import (
    AccountDeletionRequest,
    DataExportRequest,
    Referral,
    ReferralReward,
    SupportTicket,
    SupportTicketMessage,
)
from apps.profile_features.services import process_account_deletion_request, process_data_export_request
from tests.helpers import authenticated_client


def active_receipt(event_id="ref-evt-1", original_transaction_id="ref-orig-1", app_account_token="ref-token"):
    now = timezone.now()
    return {
        "event_id": event_id,
        "event_type": "development_active",
        "product_id": "patto.monthly",
        "original_transaction_id": original_transaction_id,
        "latest_transaction_id": f"{original_transaction_id}.latest",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "app_account_token": app_account_token,
    }


def create_active_couple(prefix):
    partner_one = authenticated_client(f"{prefix}-p1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": f"{prefix}-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client(f"{prefix}-p2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_referral_reward_originates_from_verified_billing_event():
    referrer = authenticated_client("referrer@example.com")
    code_response = referrer.get("/api/v1/referrals/code/")
    referred, _ = create_active_couple("referred")

    apply_response = referred.post(
        "/api/v1/referrals/apply/",
        {"code": code_response.json()["code"]},
        content_type="application/json",
    )
    assert apply_response.status_code == 201
    assert Referral.objects.get().status == Referral.Status.PENDING
    assert ReferralReward.objects.count() == 0

    billing_response = referred.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": active_receipt()},
        content_type="application/json",
    )

    referral = Referral.objects.get()
    reward = ReferralReward.objects.get()
    assert billing_response.status_code == 200
    assert referral.status == Referral.Status.REWARDED
    assert referral.verified_event is not None
    assert reward.source_event == referral.verified_event
    assert reward.metadata["origin"] == "verified_iap_event"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_support_ticket_create_and_message_are_user_scoped():
    user = authenticated_client("support-user@example.com")
    ticket_response = user.post(
        "/api/v1/support-tickets/",
        {"category": "technical", "subject": "Upload issue", "body": "My image did not upload."},
        content_type="application/json",
    )
    ticket_id = ticket_response.json()["id"]
    message_response = user.post(
        f"/api/v1/support-tickets/{ticket_id}/messages/",
        {"body": "Adding more detail."},
        content_type="application/json",
    )
    other = authenticated_client("support-other@example.com")
    other_response = other.post(
        f"/api/v1/support-tickets/{ticket_id}/messages/",
        {"body": "Not mine."},
        content_type="application/json",
    )

    assert ticket_response.status_code == 201
    assert message_response.status_code == 201
    assert other_response.status_code == 404
    assert SupportTicket.objects.count() == 1
    assert SupportTicketMessage.objects.count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_subscription_management_surface_and_request():
    partner_one, _ = create_active_couple("submgmt")
    partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "google", "receipt": active_receipt(event_id="submgmt-evt", original_transaction_id="submgmt-orig", app_account_token="submgmt-token")},
        content_type="application/json",
    )

    status_response = partner_one.get("/api/v1/subscription-management/")
    request_response = partner_one.post(
        "/api/v1/subscription-management/",
        {"request_type": "restore_help", "platform": "google", "notes": "Need restore help."},
        content_type="application/json",
    )

    assert status_response.status_code == 200
    assert status_response.json()["current_subscription"]["platform"] == "google"
    assert "google" in status_response.json()["platform_management"]
    assert request_response.status_code == 201
    assert request_response.json()["request_type"] == "restore_help"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_notification_settings_existing_surface_remains_available():
    user = authenticated_client("settings-user@example.com")

    response = user.patch(
        "/api/v1/notification-preferences/",
        {"category": "analysis_ready", "enabled": False},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["category"] == "analysis_ready"
    assert response.json()["enabled"] is False


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_data_export_and_deletion_requests_are_idempotent_intake_records():
    user = authenticated_client("privacy-user@example.com")

    first_export = user.post("/api/v1/data-export-requests/")
    second_export = user.post("/api/v1/data-export-requests/")
    first_deletion = user.post(
        "/api/v1/account-deletion-requests/",
        {"reason": "Leaving for now.", "confirmation_email": "privacy-user@example.com"},
        content_type="application/json",
    )
    second_deletion = user.post(
        "/api/v1/account-deletion-requests/",
        {"reason": "Duplicate request.", "confirmation_email": "privacy-user@example.com"},
        content_type="application/json",
    )

    assert first_export.status_code == 201
    assert second_export.status_code == 201
    assert first_export.json()["id"] == second_export.json()["id"]
    assert DataExportRequest.objects.count() == 1
    assert first_deletion.status_code == 201
    assert second_deletion.status_code == 201
    assert first_deletion.json()["id"] == second_deletion.json()["id"]
    assert AccountDeletionRequest.objects.count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_account_deletion_requires_confirmation_email():
    user = authenticated_client("confirm-delete@example.com")

    response = user.post(
        "/api/v1/account-deletion-requests/",
        {"reason": "Leaving.", "confirmation_email": "wrong@example.com"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert AccountDeletionRequest.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_data_export_processing_includes_owned_and_permitted_shared_data():
    partner_one, partner_two = create_active_couple("export")
    owner = User.objects.get(email="export-p1@example.com")
    partner = User.objects.get(email="export-p2@example.com")
    couple = Couple.objects.get(members__user=owner)
    ticket = SupportTicket.objects.create(user=owner, category=SupportTicket.Category.ACCOUNT, subject="Need my data")
    SupportTicketMessage.objects.create(ticket=ticket, user=owner, body="Please export.")

    export_request = DataExportRequest.objects.create(user=owner)
    processed = process_data_export_request(export_request=export_request)
    processed_again = process_data_export_request(export_request=processed)

    assert processed.status == DataExportRequest.Status.READY
    assert processed.checksum_sha256 == processed_again.checksum_sha256
    assert processed.byte_size > 0
    assert processed.export_data["user"]["email"] == "export-p1@example.com"
    assert processed.export_data["support_tickets"][0]["subject"] == "Need my data"
    assert processed.export_data["couples"][0]["id"] == str(couple.id)
    exported_member_emails = {member["email"] for member in processed.export_data["couples"][0]["members"]}
    assert {"export-p1@example.com", partner.email} <= exported_member_emails


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_account_deletion_processing_revokes_sessions_notifies_partner_deletes_shared_couple_and_allows_reconnect():
    partner_one, partner_two = create_active_couple("delete")
    owner = User.objects.get(email="delete-p1@example.com")
    partner = User.objects.get(email="delete-p2@example.com")
    couple = Couple.objects.get(members__user=owner)
    old_couple_id = couple.id
    partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": active_receipt(event_id="delete-evt", original_transaction_id="delete-orig", app_account_token="delete-token")},
        content_type="application/json",
    )
    export_request = DataExportRequest.objects.create(user=owner, status=DataExportRequest.Status.READY, export_data={"couples": [{"id": str(old_couple_id)}]}, byte_size=42, checksum_sha256="a" * 64)
    assert AuthSession.objects.filter(user=owner, revoked_at__isnull=True).exists()

    deletion_response = partner_one.post(
        "/api/v1/account-deletion-requests/",
        {"reason": "Privacy request.", "confirmation_email": "delete-p1@example.com"},
        content_type="application/json",
    )
    deletion_request = AccountDeletionRequest.objects.get(id=deletion_response.json()["id"])

    processed = process_account_deletion_request(deletion_request=deletion_request)
    processed_again = process_account_deletion_request(deletion_request=processed)
    owner.refresh_from_db()
    reconnect_response = partner_two.post("/api/v1/couples/")
    new_couple_id = reconnect_response.json()["id"]
    new_invitation = partner_two.post(
        f"/api/v1/couples/{new_couple_id}/invitations/",
        {"email": "new-partner@example.com"},
        content_type="application/json",
    )

    assert processed_again.status == AccountDeletionRequest.Status.COMPLETED
    assert AuthSession.objects.filter(user=owner, revoked_at__isnull=True).count() == 0
    assert Subscription.objects.filter(owner=owner).count() == 0
    assert Entitlement.objects.filter(couple_id=old_couple_id).count() == 0
    assert Couple.objects.filter(id=old_couple_id).count() == 0
    assert CoupleMember.objects.filter(couple_id=old_couple_id).count() == 0
    notification = Notification.objects.get(user=partner, category=NotificationPreference.Category.ACCOUNT_DELETION_REQUESTED)
    assert notification.couple_id is None
    assert notification.data["couple_id"] == str(old_couple_id)
    assert processed.couple_action == AccountDeletionRequest.CoupleAction.DELETED
    assert owner.email.startswith("deleted-")
    assert owner.is_active is False
    export_request.refresh_from_db()
    assert export_request.export_data == {}
    assert export_request.byte_size == 0
    assert export_request.checksum_sha256 == ""
    assert reconnect_response.status_code == 201
    assert new_invitation.status_code == 201


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_account_deletion_processing_deletes_single_member_couple():
    client = authenticated_client("solo-delete@example.com")
    owner = User.objects.get(email="solo-delete@example.com")
    couple_id = client.post("/api/v1/couples/").json()["id"]
    deletion_response = client.post(
        "/api/v1/account-deletion-requests/",
        {"reason": "Solo.", "confirmation_email": "solo-delete@example.com"},
        content_type="application/json",
    )

    processed = process_account_deletion_request(deletion_request=AccountDeletionRequest.objects.get(id=deletion_response.json()["id"]))

    assert processed.couple_action == AccountDeletionRequest.CoupleAction.DELETED
    assert Couple.objects.filter(id=couple_id).count() == 0
