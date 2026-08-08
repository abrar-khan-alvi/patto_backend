import pytest
from django.test import override_settings

from apps.topics.models import CoupleTopic, CustomQuestion
from apps.topics.services import mark_custom_topic_locked
from tests.helpers import authenticated_client


def custom_topic_payload(title="Religion & spirituality"):
    return {
        "icon": "sparkles",
        "title": title,
        "description": "Beliefs, rituals, and meaning.",
        "questions": [
            {
                "prompt": "What role should shared rituals play in our relationship?",
                "options": [{"text": "Very important"}, {"text": "Somewhat important"}, {"text": "Not important"}],
            },
            {
                "prompt": "How should we handle different beliefs?",
                "options": [{"text": "Discuss openly"}, {"text": "Keep private"}, {"text": "I am unsure"}],
            },
            {
                "prompt": "What boundary matters most in this area?",
                "options": [{"text": "Family boundaries"}, {"text": "Holiday choices"}, {"text": "Children"}],
            },
        ],
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
    return partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_active_partner_can_create_custom_topic():
    partner_one, _ = create_active_couple()

    response = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Religion & spirituality"
    assert body["version"] == 1
    assert body["question_count"] == 3
    assert CoupleTopic.objects.count() == 1
    assert CustomQuestion.objects.count() == 3


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_custom_topic_requires_minimum_questions():
    partner_one, _ = create_active_couple()
    payload = custom_topic_payload()
    payload["questions"] = payload["questions"][:2]

    response = partner_one.post("/api/v1/custom-topics/", payload, content_type="application/json")

    assert response.status_code == 400
    assert CoupleTopic.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_both_partners_can_list_and_view_same_custom_topic():
    partner_one, partner_two = create_active_couple()
    topic_id = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()["id"]

    list_response = partner_two.get("/api/v1/custom-topics/")
    detail_response = partner_two.get(f"/api/v1/custom-topics/{topic_id}/")

    assert list_response.status_code == 200
    assert len(list_response.json()["custom_topics"]) == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == topic_id


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_custom_topics_do_not_leak_across_couples():
    partner_one, _ = create_active_couple()
    topic_id = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()["id"]
    other_user = authenticated_client("other@example.com")
    other_user.post("/api/v1/couples/")

    assert other_user.get("/api/v1/custom-topics/").json()["custom_topics"] == []
    assert other_user.get(f"/api/v1/custom-topics/{topic_id}/").status_code == 404


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_unlocked_custom_topic_updates_in_place():
    partner_one, _ = create_active_couple()
    topic_id = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()["id"]
    payload = custom_topic_payload(title="Pets & animals")

    response = partner_one.put(f"/api/v1/custom-topics/{topic_id}/", payload, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["title"] == "Pets & animals"
    assert response.json()["version"] == 1
    assert CoupleTopic.objects.count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_locked_custom_topic_edit_creates_new_version():
    partner_one, _ = create_active_couple()
    topic_id = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()["id"]
    original = CoupleTopic.objects.get(id=topic_id)
    mark_custom_topic_locked(original)
    payload = custom_topic_payload(title="Religion and spirituality updated")

    response = partner_one.put(f"/api/v1/custom-topics/{topic_id}/", payload, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["supersedes"] == str(original.id)
    original.refresh_from_db()
    assert original.is_active is False
    assert CoupleTopic.objects.count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_delete_deactivates_custom_topic_without_deleting_rows():
    partner_one, _ = create_active_couple()
    topic_id = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()["id"]

    response = partner_one.delete(f"/api/v1/custom-topics/{topic_id}/")

    assert response.status_code == 204
    topic = CoupleTopic.objects.get(id=topic_id)
    assert topic.is_active is False
    assert CustomQuestion.objects.filter(topic=topic).count() == 3
