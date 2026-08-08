from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ai.models import AIAnalysisResult
from apps.analysis.models import AnalysisRun, AlignmentDimension, ConversationStarter, ProposedClause, TopicAnalysis
from apps.common.services import record_audit_event
from apps.couples.models import CoupleMember
from apps.responses.models import TopicMemberCompletion, TopicResponse
from apps.responses.services import session_is_released


@transaction.atomic
def materialize_topic_analysis(*, ai_result: AIAnalysisResult, rerun: bool = False, request_id: str = "") -> AnalysisRun:
    analysis_job = ai_result.analysis_job
    session = analysis_job.session

    existing = AnalysisRun.objects.filter(ai_result=ai_result).order_by("-version").first()
    if existing is not None and not rerun:
        return existing

    if not session_is_released(session):
        raise ValidationError({"session": "Topic analysis requires both active partners to complete and lock answers."})

    if ai_result.status != AIAnalysisResult.Status.SUCCEEDED or not ai_result.output:
        return create_recoverable_failed_run(ai_result=ai_result, request_id=request_id)

    next_version = next_analysis_version(session=session)
    active_member_ids = active_completed_member_ids(session=session)
    deterministic_similarity_score = calculate_option_similarity_score(session=session, active_member_ids=active_member_ids)
    output = ai_result.output

    run = AnalysisRun.objects.create(
        session=session,
        couple=session.couple,
        analysis_job=analysis_job,
        ai_result=ai_result,
        version=next_version,
        status=AnalysisRun.Status.SUCCEEDED,
        topic_stable_key=session.topic_stable_key,
        topic_version=session.topic_version,
        active_member_ids=[str(user_id) for user_id in active_member_ids],
        deterministic_similarity_score=deterministic_similarity_score,
        started_at=analysis_job.started_at,
        completed_at=timezone.now(),
    )
    TopicAnalysis.objects.create(
        run=run,
        summary=output["relationship_summary"],
        alignment_score=output["alignment_score"],
        confidence_score=deterministic_confidence_score(session=session),
        common_ground=output.get("strengths", []),
        differences=output.get("growth_areas", []),
        sensitive_areas=output.get("safety_notes", []),
        safety_flags=output.get("safety_notes", []),
    )
    create_alignment_dimensions(run=run, output=output, deterministic_similarity_score=deterministic_similarity_score)
    for index, prompt in enumerate(output.get("conversation_starters", []), start=1):
        ConversationStarter.objects.create(run=run, prompt=prompt, sort_order=index)
    for index, clause_text in enumerate(output.get("suggested_pact_items", []), start=1):
        ProposedClause.objects.create(run=run, clause_text=clause_text, sort_order=index)

    record_audit_event(
        action="topic_analysis.materialized",
        actor=None,
        target=session,
        request_id=request_id,
        metadata={
            "analysis_run_id": str(run.id),
            "analysis_job_id": str(analysis_job.id),
            "ai_result_id": str(ai_result.id),
            "version": run.version,
        },
    )
    return run


@transaction.atomic
def create_recoverable_failed_run(*, ai_result: AIAnalysisResult, request_id: str = "") -> AnalysisRun:
    analysis_job = ai_result.analysis_job
    session = analysis_job.session
    existing = AnalysisRun.objects.filter(ai_result=ai_result).order_by("-version").first()
    if existing is not None:
        return existing
    status = (
        AnalysisRun.Status.SAFETY_BLOCKED
        if ai_result.status == AIAnalysisResult.Status.SAFETY_BLOCKED
        else AnalysisRun.Status.FAILED
    )
    run = AnalysisRun.objects.create(
        session=session,
        couple=session.couple,
        analysis_job=analysis_job,
        ai_result=ai_result,
        version=next_analysis_version(session=session),
        status=status,
        topic_stable_key=session.topic_stable_key,
        topic_version=session.topic_version,
        active_member_ids=[str(user_id) for user_id in active_completed_member_ids(session=session)],
        failure_code=ai_result.error_code or ai_result.status,
        failure_message=ai_result.error_message or ai_result.refusal_reason,
        started_at=analysis_job.started_at,
        completed_at=timezone.now(),
    )
    record_audit_event(
        action="topic_analysis.materialization_failed",
        actor=None,
        target=session,
        request_id=request_id,
        metadata={
            "analysis_run_id": str(run.id),
            "analysis_job_id": str(analysis_job.id),
            "ai_result_id": str(ai_result.id),
            "status": run.status,
        },
    )
    return run


def next_analysis_version(*, session) -> int:
    latest = AnalysisRun.objects.filter(session=session).aggregate(max_version=Max("version"))["max_version"]
    return (latest or 0) + 1


def active_completed_member_ids(*, session) -> list:
    active_user_ids = list(
        session.couple.members.filter(status=CoupleMember.Status.ACTIVE).order_by("role", "created_at").values_list("user_id", flat=True)
    )
    completed_user_ids = set(
        TopicMemberCompletion.objects.filter(session=session, user_id__in=active_user_ids).values_list("user_id", flat=True)
    )
    return [user_id for user_id in active_user_ids if user_id in completed_user_ids]


def calculate_option_similarity_score(*, session, active_member_ids: list) -> int:
    if len(active_member_ids) < 2:
        return 0
    responses = TopicResponse.objects.filter(
        session=session,
        user_id__in=active_member_ids,
    ).exclude(selected_option_key="")
    by_question = {}
    for response in responses:
        by_question.setdefault(response.question_stable_key, {})[response.user_id] = response.selected_option_key
    comparable = 0
    matches = 0
    for answers_by_user in by_question.values():
        if all(user_id in answers_by_user for user_id in active_member_ids):
            comparable += 1
            if len({answers_by_user[user_id] for user_id in active_member_ids}) == 1:
                matches += 1
    if comparable == 0:
        return 0
    return round((matches / comparable) * 100)


def deterministic_confidence_score(*, session) -> int:
    expected_responses = session.expected_question_count * 2
    actual_responses = TopicResponse.objects.filter(session=session).count()
    if expected_responses == 0:
        return 0
    return min(100, round((actual_responses / expected_responses) * 100))


def create_alignment_dimensions(*, run: AnalysisRun, output: dict, deterministic_similarity_score: int) -> None:
    dimensions = [
        (
            "Answer similarity",
            deterministic_similarity_score,
            "Deterministic comparison of both partners' selected options on matching questions.",
        ),
        (
            "AI interpreted alignment",
            output["alignment_score"],
            "Structured AI interpretation of alignment across the completed topic.",
        ),
    ]
    for index, (label, score, explanation) in enumerate(dimensions, start=1):
        AlignmentDimension.objects.create(
            run=run,
            label=label,
            score=score,
            explanation=explanation,
            sort_order=index,
        )
