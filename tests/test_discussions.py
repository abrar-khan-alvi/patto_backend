import pytest
from django.test import override_settings

from apps.discussions.models import DiscussionMessage, MediationRequest
from apps.discussions.services import record_mediation_failure, record_mediation_success
from tests.helpers import authenticated_client
from tests.test_private_responses import create_active_couple


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_both_active_partners_can_create_thread_and_messages():
    partner_one, partner_two = create_active_couple()
    session_id = create_session_id(partner_one)

    created = partner_one.post(
        "/api/v1/discussion-threads/",
        {"session_id": session_id, "title": "Money discussion"},
        content_type="application/json",
    )
    thread_id = created.json()["id"]
    message = partner_two.post(
        f"/api/v1/discussion-threads/{thread_id}/messages/",
        {"body": "I want to discuss this gently."},
        content_type="application/json",
    )

    assert created.status_code == 201
    assert message.status_code == 201
    assert message.json()["sender_type"] == DiscussionMessage.SenderType.USER
    assert message.json()["body"] == "I want to discuss this gently."


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_cross_couple_user_cannot_access_or_write_discussion_thread():
    partner_one, _partner_two = create_active_couple()
    session_id = create_session_id(partner_one)
    thread_id = partner_one.post(
        "/api/v1/discussion-threads/",
        {"session_id": session_id},
        content_type="application/json",
    ).json()["id"]
    outsider = authenticated_client("discussion-outsider@example.com")
    outsider.post("/api/v1/couples/")

    read = outsider.get(f"/api/v1/discussion-threads/{thread_id}/")
    write = outsider.post(
        f"/api/v1/discussion-threads/{thread_id}/messages/",
        {"body": "I should not be here."},
        content_type="application/json",
    )

    assert read.status_code == 404
    assert write.status_code == 404


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_user_message_content_is_escaped_as_text_not_raw_html():
    partner_one, _partner_two = create_active_couple()
    session_id = create_session_id(partner_one)
    thread_id = partner_one.post(
        "/api/v1/discussion-threads/",
        {"session_id": session_id},
        content_type="application/json",
    ).json()["id"]

    response = partner_one.post(
        f"/api/v1/discussion-threads/{thread_id}/messages/",
        {"body": "<script>alert('x')</script>"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["body"] == "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;"
    assert response.json()["metadata"]["render_as"] == "text"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_mediation_failure_does_not_delete_user_messages():
    partner_one, _partner_two = create_active_couple()
    session_id = create_session_id(partner_one)
    thread_id = partner_one.post(
        "/api/v1/discussion-threads/",
        {"session_id": session_id},
        content_type="application/json",
    ).json()["id"]
    partner_one.post(
        f"/api/v1/discussion-threads/{thread_id}/messages/",
        {"body": "Please help us mediate."},
        content_type="application/json",
    )
    mediation = partner_one.post(f"/api/v1/discussion-threads/{thread_id}/mediation-requests/")

    mediation_request = MediationRequest.objects.get(id=mediation.json()["id"])
    record_mediation_failure(
        mediation_request=mediation_request,
        failure_code="provider_error",
        failure_message="AI provider failed.",
    )

    detail = partner_one.get(f"/api/v1/discussion-threads/{thread_id}/")
    assert mediation.status_code == 201
    assert DiscussionMessage.objects.filter(thread_id=thread_id).count() == 1
    assert detail.json()["messages"][0]["body"] == "Please help us mediate."
    assert MediationRequest.objects.get(id=mediation_request.id).status == MediationRequest.Status.FAILED


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_mediation_success_creates_clearly_identified_ai_message():
    partner_one, _partner_two = create_active_couple()
    session_id = create_session_id(partner_one)
    thread_id = partner_one.post(
        "/api/v1/discussion-threads/",
        {"session_id": session_id},
        content_type="application/json",
    ).json()["id"]
    mediation = partner_one.post(f"/api/v1/discussion-threads/{thread_id}/mediation-requests/")
    mediation_request = MediationRequest.objects.get(id=mediation.json()["id"])

    response = record_mediation_success(
        mediation_request=mediation_request,
        content="Try reflecting each other's concern before proposing a solution.",
        model="test-model",
    )

    detail = partner_one.get(f"/api/v1/discussion-threads/{thread_id}/")
    ai_messages = [message for message in detail.json()["messages"] if message["sender_type"] == "ai"]
    assert response.message.sender_type == DiscussionMessage.SenderType.AI
    assert len(ai_messages) == 1
    assert ai_messages[0]["metadata"]["mediation_request_id"] == str(mediation_request.id)


def create_session_id(client):
    from apps.topics.models import Topic

    topic = Topic.objects.get(slug="money")
    response = client.post(
        "/api/v1/topic-sessions/",
        {"topic_kind": "built_in", "topic_id": str(topic.id)},
        content_type="application/json",
    )
    assert response.status_code == 201
    return response.json()["id"]
