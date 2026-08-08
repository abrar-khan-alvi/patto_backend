from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.billing.models import Subscription, SubscriptionEvent
from apps.couples.models import Entitlement
from tests.helpers import authenticated_client


def active_receipt(event_id="evt-1", original_transaction_id="orig-1"):
    now = timezone.now()
    return {
        "event_id": event_id,
        "event_type": "development_active",
        "product_id": "patto.monthly",
        "original_transaction_id": original_transaction_id,
        "latest_transaction_id": f"{original_transaction_id}.latest",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "app_account_token": "dev-account-token",
    }


def expired_receipt(event_id="evt-expired", original_transaction_id="orig-1"):
    now = timezone.now()
    return {
        "event_id": event_id,
        "event_type": "expiration",
        "product_id": "patto.monthly",
        "original_transaction_id": original_transaction_id,
        "latest_transaction_id": f"{original_transaction_id}.expired",
        "starts_at": (now - timedelta(days=40)).isoformat(),
        "expires_at": (now - timedelta(days=1)).isoformat(),
        "app_account_token": "dev-account-token",
    }


def create_active_couple():
    partner_one = authenticated_client("partner1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client("partner2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return couple_id, partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_one_can_apply_development_iap_receipt():
    _, partner_one, _ = create_active_couple()

    response = partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": active_receipt()},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["status"] == Subscription.Status.ACTIVE
    assert body["entitlement"]["active"] is True
    assert Entitlement.objects.filter(source=Entitlement.Source.APPLE_IAP).count() == 1
    assert SubscriptionEvent.objects.filter(status=SubscriptionEvent.Status.PROCESSED).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_development_iap_event_processing_is_idempotent():
    _, partner_one, _ = create_active_couple()
    receipt = active_receipt()

    first = partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": receipt},
        content_type="application/json",
    )
    second = partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": receipt},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert Subscription.objects.count() == 1
    assert SubscriptionEvent.objects.count() == 1
    assert Entitlement.objects.count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_two_cannot_attach_iap_billing():
    _, _, partner_two = create_active_couple()

    response = partner_two.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "google", "receipt": active_receipt()},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert Subscription.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_expired_iap_receipt_removes_active_entitlement():
    _, partner_one, _ = create_active_couple()
    partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": active_receipt()},
        content_type="application/json",
    )

    response = partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "apple", "receipt": expired_receipt()},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["subscription"]["status"] == Subscription.Status.EXPIRED
    assert Entitlement.objects.get().is_active() is False


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_current_entitlement_endpoint_returns_access_state():
    _, partner_one, partner_two = create_active_couple()
    before_response = partner_two.get("/api/v1/billing/entitlement/current/")
    assert before_response.status_code == 200
    assert before_response.json()["has_active_entitlement"] is False

    partner_one.post(
        "/api/v1/billing/iap/development/verify/",
        {"platform": "google", "receipt": active_receipt(original_transaction_id="google-orig")},
        content_type="application/json",
    )
    after_response = partner_two.get("/api/v1/billing/entitlement/current/")

    assert after_response.status_code == 200
    assert after_response.json()["has_active_entitlement"] is True
