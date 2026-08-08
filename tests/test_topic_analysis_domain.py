import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ai.client import AIClientResponse
from apps.ai.models import AIAnalysisResult
from apps.ai.services import run_topic_analysis
from apps.analysis.models import AnalysisRun, AlignmentDimension, ConversationStarter, ProposedClause, TopicAnalysis
from apps.analysis.services import create_recoverable_failed_run, materialize_topic_analysis
from apps.responses.models import TopicAnalysisJob, TopicSession
from tests.helpers import authenticated_client
from tests.test_ai_analysis import FakeTopicAnalysisClient, valid_topic_analysis_output
from tests.test_private_responses import answers_for_topic, create_active_couple, create_built_in_session


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", OPENAI_MODEL="test-model")
def test_successful_ai_result_materializes_topic_analysis_domain_tables():
    partner_one, _partner_two, analysis_job = completed_job_with_matching_options()
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_topic_analysis_output()))

    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    run = AnalysisRun.objects.get(ai_result=result)
    topic_analysis = TopicAnalysis.objects.get(run=run)
    assert run.status == AnalysisRun.Status.SUCCEEDED
    assert run.version == 1
    assert run.topic_stable_key == analysis_job.session.topic_stable_key
    assert len(run.active_member_ids) == 2
    assert run.deterministic_similarity_score == 100
    assert topic_analysis.alignment_score == 82
    assert topic_analysis.common_ground == ["Both partners are engaged."]
    assert AlignmentDimension.objects.filter(run=run).count() == 2
    assert ConversationStarter.objects.filter(run=run).count() == 1
    assert ProposedClause.objects.filter(run=run).count() == 1

    response = partner_one.get(f"/api/v1/topic-sessions/{analysis_job.session_id}/analysis/")
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["topic_analysis"]["alignment_score"] == 82


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_analysis_rerun_creates_new_version():
    _partner_one, _partner_two, analysis_job = completed_job_with_matching_options()
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_topic_analysis_output()))
    result = run_topic_analysis(analysis_job_id=analysis_job.id, client=client)

    first_run = materialize_topic_analysis(ai_result=result)
    second_run = materialize_topic_analysis(ai_result=result, rerun=True)

    assert first_run.version == 1
    assert second_run.version == 2
    assert AnalysisRun.objects.filter(session=analysis_job.session).count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_failed_ai_result_creates_recoverable_failed_analysis_run():
    _partner_one, _partner_two, analysis_job = completed_job_with_matching_options()
    ai_result = AIAnalysisResult.objects.create(
        analysis_job=analysis_job,
        status=AIAnalysisResult.Status.FAILED,
        model="test-model",
        error_code="provider_error",
        error_message="Provider failed.",
    )

    run = create_recoverable_failed_run(ai_result=ai_result)

    assert run.status == AnalysisRun.Status.FAILED
    assert run.failure_code == "provider_error"
    assert run.failure_message == "Provider failed."


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_analysis_requires_both_answer_sets_locked():
    partner_one, _ = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers_for_topic(topic, text_prefix="p1")},
        content_type="application/json",
    )
    session = TopicSession.objects.get(id=session_body["id"])
    analysis_job = TopicAnalysisJob.objects.create(
        session=session,
        couple=session.couple,
        queued_at=timezone.now(),
    )
    ai_result = AIAnalysisResult.objects.create(
        analysis_job=analysis_job,
        status=AIAnalysisResult.Status.SUCCEEDED,
        model="test-model",
        output=valid_topic_analysis_output(),
    )

    with pytest.raises(ValidationError):
        materialize_topic_analysis(ai_result=ai_result)


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_cross_couple_user_cannot_read_materialized_analysis():
    partner_one, _partner_two, analysis_job = completed_job_with_matching_options()
    client = FakeTopicAnalysisClient(AIClientResponse(content=valid_topic_analysis_output()))
    run_topic_analysis(analysis_job_id=analysis_job.id, client=client)
    outsider = authenticated_client("outsider-analysis@example.com")
    outsider.post("/api/v1/couples/")

    outsider_response = outsider.get(f"/api/v1/topic-sessions/{analysis_job.session_id}/analysis/")
    partner_response = partner_one.get(f"/api/v1/topic-sessions/{analysis_job.session_id}/analysis/")

    assert outsider_response.status_code == 404
    assert partner_response.status_code == 200


def completed_job_with_matching_options():
    partner_one, partner_two = create_active_couple()
    session_body, topic = create_built_in_session(partner_one)
    answers = answers_for_topic(topic)
    partner_one.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers},
        content_type="application/json",
    )
    partner_two.post(
        f"/api/v1/topic-sessions/{session_body['id']}/complete/",
        {"answers": answers},
        content_type="application/json",
    )
    return partner_one, partner_two, TopicAnalysisJob.objects.get(session_id=session_body["id"])
