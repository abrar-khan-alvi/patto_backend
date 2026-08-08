import pytest
from django.test import override_settings

from apps.accounts.models import User
from apps.responses.models import TopicAnalysisJob, TopicMemberCompletion, TopicResponse, TopicSession, TopicSyncEvent
from apps.responses.services import mark_analysis_job_succeeded, synchronize_partner_completion
from apps.topics.models import CoupleTopic, Topic
from tests.helpers import authenticated_client
from tests.test_custom_topics import custom_topic_payload


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


def create_built_in_session(client, slug="money"):
    topic = Topic.objects.get(slug=slug)
    response = client.post(
        "/api/v1/topic-sessions/",
        {"topic_kind": "built_in", "topic_id": str(topic.id)},
        content_type="application/json",
    )
    assert response.status_code == 201
    return response.json(), topic


def answers_for_topic(topic, limit=None, text_prefix="answer"):
    questions = list(topic.questions.filter(is_active=True).order_by("sort_order"))
    if limit is not None:
        questions = questions[:limit]
    answers = []
    for question in questions:
        option = question.options.order_by("sort_order").first()
        answers.append(
            {
                "question_id": str(question.id),
                "selected_option_id": str(option.id),
                "text_answer": f"{text_prefix} {question.sort_order}",
            }
        )
    return answers


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_create_topic_session_freezes_topic_version_and_question_count():
    partner_one, _ = create_active_couple()

    body, topic = create_built_in_session(partner_one)

    assert body["topic_stable_key"] == topic.stable_key
    assert body["topic_version"] == topic.version
    assert body["expected_question_count"] == 12
    assert TopicSession.objects.count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_save_partial_answers_does_not_complete_topic():
    partner_one, _ = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)

    response = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/answers/",
        {"answers": answers_for_topic(topic, limit=2)},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert len(response.json()["responses"]) == 2
    assert TopicResponse.objects.count() == 2
    assert TopicMemberCompletion.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_completion_requires_all_answers_and_locks_user_answers():
    partner_one, _ = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)

    incomplete = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, limit=2)},
        content_type="application/json",
    )
    assert incomplete.status_code == 400

    complete = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic)},
        content_type="application/json",
    )
    assert complete.status_code == 200
    assert TopicMemberCompletion.objects.count() == 1

    locked = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/answers/",
        {"answers": answers_for_topic(topic, limit=1, text_prefix="changed")},
        content_type="application/json",
    )
    assert locked.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_responses_are_private_until_both_complete():
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p1")},
        content_type="application/json",
    )

    partner_view = partner_two.get(f"/api/v1/topic-sessions/{session_body['id']}/")
    owner_view = partner_one.get(f"/api/v1/topic-sessions/{session_body['id']}/")

    assert partner_view.status_code == 200
    assert partner_view.json()["is_released"] is False
    assert partner_view.json()["responses"] == []
    assert len(owner_view.json()["responses"]) == 12


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_responses_release_after_both_partners_complete():
    partner_one, partner_two = create_active_couple()
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

    response = partner_one.get(f"/api/v1/topic-sessions/{session_body['id']}/")

    assert response.status_code == 200
    assert response.json()["is_released"] is True
    assert len(response.json()["responses"]) == 24


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_first_partner_completion_records_waiting_sync_for_other_partner():
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)

    response = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p1")},
        content_type="application/json",
    )
    partner_two_view = partner_two.get(f"/api/v1/topic-sessions/{session_body['id']}/")

    partner_two_user = User.objects.get(email="partner2@example.com")
    assert response.status_code == 200
    assert response.json()["sync"]["waiting_for_partner"] is True
    assert response.json()["sync"]["analysis_job"] is None
    assert partner_two_view.json()["sync"]["partner_is_waiting_for_you"] is True
    assert TopicAnalysisJob.objects.count() == 0
    assert TopicSyncEvent.objects.filter(
        user=partner_two_user,
        event_type=TopicSyncEvent.EventType.PARTNER_COMPLETED_WAITING,
    ).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_both_partner_completion_queues_exactly_one_analysis_job():
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    session = TopicSession.objects.get(id=session_body["id"])

    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p1")},
        content_type="application/json",
    )
    response = partner_two.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p2")},
        content_type="application/json",
    )

    completion = TopicMemberCompletion.objects.get(session=session, user__email="partner2@example.com")
    synchronize_partner_completion(session=session, completion=completion, request_id="retry")

    assert response.status_code == 200
    assert response.json()["sync"]["is_released"] is True
    assert response.json()["sync"]["analysis_job"]["status"] == TopicAnalysisJob.Status.QUEUED
    assert TopicAnalysisJob.objects.filter(session=session).count() == 1
    assert TopicSyncEvent.objects.filter(session=session, event_type=TopicSyncEvent.EventType.ANALYSIS_QUEUED).count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_analysis_success_records_ready_sync_for_both_partners_idempotently():
    partner_one, partner_two = create_active_couple()
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

    analysis_job = TopicAnalysisJob.objects.get(session_id=session_body["id"])
    mark_analysis_job_succeeded(analysis_job=analysis_job)
    mark_analysis_job_succeeded(analysis_job=analysis_job)

    analysis_job.refresh_from_db()
    assert analysis_job.status == TopicAnalysisJob.Status.SUCCEEDED
    assert TopicSyncEvent.objects.filter(
        session_id=session_body["id"],
        event_type=TopicSyncEvent.EventType.ANALYSIS_READY,
    ).count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_answer_retries_update_existing_response_without_duplicates():
    partner_one, _ = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    question = topic.questions.filter(is_active=True).order_by("sort_order").first()
    option = question.options.order_by("sort_order").first()
    answer = {"question_id": str(question.id), "selected_option_id": str(option.id), "text_answer": "first"}

    first = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/answers/",
        {"answers": [answer]},
        content_type="application/json",
    )
    answer["text_answer"] = "second"
    second = partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/answers/",
        {"answers": [answer]},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert TopicResponse.objects.count() == 1
    assert TopicResponse.objects.get().text_answer == "second"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_custom_topic_session_locks_topic_to_prevent_silent_rewrites():
    partner_one, _ = create_active_couple()
    topic_body = partner_one.post(
        "/api/v1/custom-topics/",
        custom_topic_payload(),
        content_type="application/json",
    ).json()

    response = partner_one.post(
        "/api/v1/topic-sessions/",
        {"topic_kind": "custom", "topic_id": topic_body["id"]},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert CoupleTopic.objects.get(id=topic_body["id"]).is_locked is True


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_cross_couple_user_cannot_access_topic_session():
    partner_one, _ = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    outsider = authenticated_client("outsider@example.com")
    outsider.post("/api/v1/couples/")

    read_response = outsider.get(f"/api/v1/topic-sessions/{session_body['id']}/")
    write_response = outsider.post(
        f"/api/v1/topic-sessions/{session_body['id']}/answers/",
        {"answers": answers_for_topic(topic, limit=1)},
        content_type="application/json",
    )

    assert read_response.status_code == 404
    assert write_response.status_code == 403
