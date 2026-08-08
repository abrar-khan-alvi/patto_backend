import pytest
from django.test import override_settings

from apps.ai.client import AIClientResponse
from apps.ai.models import AIAnalysisResult, AIFollowUpQuestion, AISafetyEvent
from apps.ai.services import generate_follow_up_question, run_topic_analysis
from apps.responses.models import TopicAnalysisJob, TopicSyncEvent
from tests.test_private_responses import answers_for_topic, create_active_couple, create_built_in_session


class FakeTopicAnalysisClient:
    def __init__(self, response: AIClientResponse):
        self.response = response
        self.calls = []

    def create_topic_analysis(self, *, model, input_messages, json_schema):
        self.calls.append({"model": model, "input_messages": input_messages, "json_schema": json_schema})
        return self.response

    def create_follow_up_question(self, *, model, input_messages, json_schema):
        self.calls.append({"model": model, "input_messages": input_messages, "json_schema": json_schema})
        return self.response


def completed_analysis_job():
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
    return TopicAnalysisJob.objects.get(session_id=session_body["id"])


def valid_topic_analysis_output():
    return {
        "relationship_summary": "Both partners care about the topic and show room for clearer expectations.",
        "alignment_score": 82,
        "strengths": ["Both partners are engaged."],
        "growth_areas": ["Clarify expectations before making commitments."],
        "conversation_starters": ["What would make this topic feel safer to discuss?"],
        "suggested_pact_items": ["Schedule a weekly 20-minute check-in."],
        "safety_notes": [],
    }


def valid_follow_up_output():
    return {
        "follow_up_question": "What would help you feel clearer and safer discussing this topic?",
        "internal_reason": "The user's answers mention wanting more clarity and emotional safety.",
        "topic_stable_key": "money",
        "topic_version": 1,
        "skip": False,
        "skip_reason": "",
    }


def answers_with_first_text(topic, text):
    answers = answers_for_topic(topic)
    answers[0]["text_answer"] = text
    return answers


def completed_analysis_job_with_safety_text(text):
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_with_first_text(topic, text)},
        content_type="application/json",
    )
    partner_two.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p2")},
        content_type="application/json",
    )
    return TopicAnalysisJob.objects.get(session_id=session_body["id"])


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", OPENAI_MODEL="test-model")
def test_topic_analysis_success_validates_and_stores_structured_output():
    analysis_job = completed_analysis_job()
    client = FakeTopicAnalysisClient(
        AIClientResponse(
            content=valid_topic_analysis_output(),
            provider_response_id="resp_test_123",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        )
    )

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client, request_id="test-request")

    analysis_job.refresh_from_db()
    assert result.status == AIAnalysisResult.Status.SUCCEEDED
    assert result.output["alignment_score"] == 82
    assert result.model == "test-model"
    assert result.provider_response_id == "resp_test_123"
    assert result.total_tokens == 30
    assert result.prompt_version.key == "topic_analysis"
    assert analysis_job.status == TopicAnalysisJob.Status.SUCCEEDED
    assert TopicSyncEvent.objects.filter(
        session=analysis_job.session,
        event_type=TopicSyncEvent.EventType.ANALYSIS_READY,
    ).count() == 2
    assert client.calls[0]["json_schema"]["type"] == "object"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_invalid_ai_output_is_not_stored_as_successful_output():
    analysis_job = completed_analysis_job()
    client = FakeTopicAnalysisClient(AIClientResponse(content={"relationship_summary": ""}))

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    analysis_job.refresh_from_db()
    assert result.status == AIAnalysisResult.Status.INVALID_OUTPUT
    assert result.output is None
    assert result.error_code == "invalid_output"
    assert analysis_job.status == TopicAnalysisJob.Status.FAILED


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_ai_refusal_is_distinguished_from_provider_failure():
    analysis_job = completed_analysis_job()
    client = FakeTopicAnalysisClient(
        AIClientResponse(content=None, provider_response_id="resp_refusal", refusal_reason="Cannot comply.")
    )

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    assert result.status == AIAnalysisResult.Status.REFUSED
    assert result.refusal_reason == "Cannot comply."
    assert result.error_code == ""


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", OPENAI_API_KEY="")
def test_missing_openai_key_records_configuration_failure_without_exposing_secret():
    analysis_job = completed_analysis_job()

    result = run_topic_analysis(analysis_job_id=analysis_job.id)

    assert result.status == AIAnalysisResult.Status.FAILED
    assert result.error_code == "configuration_error"
    assert "OPENAI_API_KEY" in result.error_message
    assert "sk-" not in result.error_message


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Sometimes I think I should kill myself.", AISafetyEvent.Category.SELF_HARM),
        ("I will kill my partner if they leave.", AISafetyEvent.Category.THREAT),
        ("I want to force my partner to do what I want.", AISafetyEvent.Category.ABUSE_COERCION),
        ("This includes minor sexual content.", AISafetyEvent.Category.MINORS),
    ],
)
def test_high_risk_input_routes_to_restricted_safety_response_without_provider_call(text, category):
    analysis_job = completed_analysis_job_with_safety_text(text)
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_topic_analysis_output()))

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    analysis_job.refresh_from_db()
    safety_event = AISafetyEvent.objects.get(analysis_job=analysis_job, category=category)
    assert result.status == AIAnalysisResult.Status.SAFETY_BLOCKED
    assert result.output["safety_notes"]
    assert analysis_job.status == TopicAnalysisJob.Status.FAILED
    assert client.calls == []
    assert safety_event.stage == AISafetyEvent.Stage.INPUT
    assert safety_event.metadata["raw_text_retained"] is False
    assert text not in str(safety_event.metadata)
    assert safety_event.content_fingerprint
    assert TopicSyncEvent.objects.filter(
        session=analysis_job.session,
        event_type=TopicSyncEvent.EventType.ANALYSIS_READY,
    ).count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_caution_input_is_audited_but_can_continue_to_normal_analysis():
    analysis_job = completed_analysis_job_with_safety_text("We need legal advice about future plans.")
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_topic_analysis_output()))

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    assert result.status == AIAnalysisResult.Status.SUCCEEDED
    assert len(client.calls) == 1
    assert AISafetyEvent.objects.filter(
        analysis_job=analysis_job,
        category=AISafetyEvent.Category.MEDICAL_LEGAL,
        route=AISafetyEvent.Route.NORMAL,
    ).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_unsafe_ai_suggestions_are_blocked_before_successful_analysis_storage():
    analysis_job = completed_analysis_job()
    output = valid_topic_analysis_output()
    output["suggested_pact_items"] = ["Track my partner so they cannot leave without telling me."]
    client = FakeTopicAnalysisClient(AIClientResponse(content=output, provider_response_id="resp_unsafe"))

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    analysis_job.refresh_from_db()
    assert result.status == AIAnalysisResult.Status.SAFETY_BLOCKED
    assert result.provider_response_id == "resp_unsafe"
    assert result.output["safety_notes"]
    assert analysis_job.status == TopicAnalysisJob.Status.FAILED
    assert AISafetyEvent.objects.filter(
        analysis_job=analysis_job,
        stage=AISafetyEvent.Stage.OUTPUT,
        category=AISafetyEvent.Category.ABUSE_COERCION,
    ).count() == 1
    assert TopicSyncEvent.objects.filter(
        session=analysis_job.session,
        event_type=TopicSyncEvent.EventType.ANALYSIS_READY,
    ).count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", OPENAI_MODEL="test-model")
def test_follow_up_uses_only_current_user_answers_and_persists_result():
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="private-one")},
        content_type="application/json",
    )
    partner_two.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="partner-secret")},
        content_type="application/json",
    )
    analysis_job = TopicAnalysisJob.objects.get(session_id=session_body["id"])
    session = analysis_job.session
    user = session.completions.get(user__email="partner1@example.com").user
    client = FakeTopicAnalysisClient(
        AIClientResponse(
            content=valid_follow_up_output(),
            provider_response_id="resp_follow_up",
            usage={"input_tokens": 4, "output_tokens": 5, "total_tokens": 9},
        )
    )

    follow_up = generate_follow_up_question(session=session, user=user, client=client)

    prompt_payload = client.calls[0]["input_messages"][2]["content"]
    assert follow_up.status == AIFollowUpQuestion.Status.SUCCEEDED
    assert follow_up.follow_up_question.startswith("What would help")
    assert follow_up.provider_response_id == "resp_follow_up"
    assert follow_up.total_tokens == 9
    assert "private-one" in prompt_payload
    assert "partner-secret" not in prompt_payload
    assert AIFollowUpQuestion.objects.filter(session=session, user=user).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_follow_up_is_not_regenerated_on_refresh():
    analysis_job = completed_analysis_job()
    user = analysis_job.session.completions.get(user__email="partner1@example.com").user
    first_client = FakeTopicAnalysisClient(AIClientResponse(content=valid_follow_up_output()))
    second_output = valid_follow_up_output()
    second_output["follow_up_question"] = "This should not replace the first question."
    second_client = FakeTopicAnalysisClient(AIClientResponse(content=second_output))

    first = generate_follow_up_question(session=analysis_job.session, user=user, client=first_client)
    second = generate_follow_up_question(session=analysis_job.session, user=user, client=second_client)

    assert first.id == second.id
    assert second.follow_up_question == first.follow_up_question
    assert len(first_client.calls) == 1
    assert second_client.calls == []


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_invalid_follow_up_output_is_persisted_without_success():
    analysis_job = completed_analysis_job()
    user = analysis_job.session.completions.get(user__email="partner1@example.com").user
    client = FakeTopicAnalysisClient(AIClientResponse(content={"skip": False}))

    follow_up = generate_follow_up_question(session=analysis_job.session, user=user, client=client)

    assert follow_up.status == AIFollowUpQuestion.Status.INVALID_OUTPUT
    assert follow_up.follow_up_question == ""
    assert follow_up.error_code == "invalid_output"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_high_risk_follow_up_input_is_safety_blocked_without_provider_call():
    analysis_job = completed_analysis_job_with_safety_text("I might hurt myself after this conversation.")
    user = analysis_job.session.completions.get(user__email="partner1@example.com").user
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_follow_up_output()))

    follow_up = generate_follow_up_question(session=analysis_job.session, user=user, client=client)

    assert follow_up.status == AIFollowUpQuestion.Status.SAFETY_BLOCKED
    assert follow_up.skip is True
    assert follow_up.error_code == "safety_policy_blocked"
    assert client.calls == []
