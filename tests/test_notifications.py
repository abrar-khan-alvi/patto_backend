import pytest
from django.test import override_settings

from apps.notifications.models import Device, Notification, NotificationDelivery, NotificationPreference
from apps.notifications.services import emit_notification
from tests.helpers import authenticated_client
from tests.test_pacts import activate_pact, create_pact
from tests.test_private_responses import answers_for_topic, create_active_couple, create_built_in_session


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_device_tokens_can_be_registered_and_revoked():
    client = authenticated_client("device@example.com")

    created = client.post(
        "/api/v1/devices/",
        {"platform": "ios", "token": "device-token-1", "name": "Abrar iPhone"},
        content_type="application/json",
    )
    revoked = client.post(f"/api/v1/devices/{created.json()['id']}/revoke/")

    assert created.status_code == 201
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False
    assert Device.objects.get(id=created.json()["id"]).revoked_at is not None


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_disabled_notification_category_is_respected():
    client = authenticated_client("prefs@example.com")
    user = Device.objects.model._meta.get_field("user").remote_field.model.objects.get(email="prefs@example.com")
    client.post(
        "/api/v1/devices/",
        {"platform": "ios", "token": "prefs-token"},
        content_type="application/json",
    )
    preference = client.patch(
        "/api/v1/notification-preferences/",
        {"category": "analysis_ready", "enabled": False},
        content_type="application/json",
    )

    result = emit_notification(
        user=user,
        category=NotificationPreference.Category.ANALYSIS_READY,
        event_key="analysis-ready-disabled",
        title="Analysis ready",
        body="Should be suppressed.",
    )

    notification = Notification.objects.get(event_key="analysis-ready-disabled")
    assert preference.status_code == 200
    assert preference.json()["enabled"] is False
    assert result is None
    assert notification.status == Notification.Status.SUPPRESSED
    assert NotificationDelivery.objects.get(notification=notification).status == NotificationDelivery.Status.SUPPRESSED


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_notification_retries_do_not_duplicate_notifications_or_deliveries():
    client = authenticated_client("retry-notifications@example.com")
    user = Device.objects.model._meta.get_field("user").remote_field.model.objects.get(email="retry-notifications@example.com")
    client.post(
        "/api/v1/devices/",
        {"platform": "android", "token": "retry-device-token"},
        content_type="application/json",
    )

    first = emit_notification(
        user=user,
        category=NotificationPreference.Category.PACT_ACTIVATED,
        event_key="pact-activated-retry",
        title="Pact live",
        body="Your pact is live.",
    )
    second = emit_notification(
        user=user,
        category=NotificationPreference.Category.PACT_ACTIVATED,
        event_key="pact-activated-retry",
        title="Pact live",
        body="Your pact is live.",
    )

    assert first.id == second.id
    assert Notification.objects.filter(event_key="pact-activated-retry").count() == 1
    assert NotificationDelivery.objects.filter(notification=first).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_join_topic_completed_and_analysis_ready_notifications_are_created():
    partner_one = authenticated_client("notify-p1@example.com")
    partner_one.post(
        "/api/v1/devices/",
        {"platform": "ios", "token": "notify-p1-device"},
        content_type="application/json",
    )
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "notify-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client("notify-p2@example.com")
    partner_two.post(
        "/api/v1/devices/",
        {"platform": "ios", "token": "notify-p2-device"},
        content_type="application/json",
    )
    partner_two.post("/api/v1/couples/invitations/accept/", {"token": token}, content_type="application/json")

    session_body, topic = create_built_in_session(partner_one)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p1")},
        content_type="application/json",
    )
    partner_two.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p2")},
        content_type="application/json",
    )
    from apps.responses.models import TopicAnalysisJob
    from apps.responses.services import mark_analysis_job_succeeded

    mark_analysis_job_succeeded(analysis_job=TopicAnalysisJob.objects.get(session_id=session_body["id"]))

    categories = set(Notification.objects.values_list("category", flat=True))
    assert NotificationPreference.Category.PARTNER_JOINED in categories
    assert NotificationPreference.Category.TOPIC_COMPLETED in categories
    assert NotificationPreference.Category.ANALYSIS_READY in categories
    assert NotificationDelivery.objects.filter(status=NotificationDelivery.Status.PENDING).exists()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_pact_approval_required_and_activated_notifications_are_created():
    partner_one, partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")
    partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    partner_two.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    categories = list(Notification.objects.values_list("category", flat=True))
    assert NotificationPreference.Category.PACT_APPROVAL_REQUIRED in categories
    assert categories.count(NotificationPreference.Category.PACT_ACTIVATED) == 2
