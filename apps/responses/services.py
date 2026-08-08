from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.common.services import record_audit_event
from apps.couples.models import Couple, CoupleMember
from apps.couples.permissions import user_is_active_couple_member
from apps.responses.models import TopicAnalysisJob, TopicMemberCompletion, TopicResponse, TopicSession, TopicSyncEvent
from apps.topics.models import CoupleTopic, CustomQuestion, CustomQuestionOption, Question, QuestionOption, Topic
from apps.topics.services import mark_custom_topic_locked


@dataclass(frozen=True)
class ResolvedTopic:
    kind: str
    stable_key: str
    version: int
    built_in_topic: Topic | None = None
    custom_topic: CoupleTopic | None = None


def ensure_active_member(*, user: User, couple: Couple) -> None:
    if not user_is_active_couple_member(user, couple):
        raise PermissionDenied("Only active couple members can answer this topic.")


def resolve_topic_for_couple(*, couple: Couple, topic_kind: str, topic_id) -> ResolvedTopic:
    if topic_kind == TopicSession.TopicKind.BUILT_IN:
        topic = Topic.objects.get(id=topic_id, is_active=True)
        return ResolvedTopic(
            kind=TopicSession.TopicKind.BUILT_IN,
            stable_key=topic.stable_key,
            version=topic.version,
            built_in_topic=topic,
        )
    if topic_kind == TopicSession.TopicKind.CUSTOM:
        topic = CoupleTopic.objects.get(id=topic_id, couple=couple, is_active=True)
        return ResolvedTopic(
            kind=TopicSession.TopicKind.CUSTOM,
            stable_key=topic.stable_key,
            version=topic.version,
            custom_topic=topic,
        )
    raise ValidationError({"topic_kind": "Unsupported topic kind."})


@transaction.atomic
def get_or_create_topic_session(*, couple: Couple, user: User, topic_kind: str, topic_id, request_id: str = "") -> TopicSession:
    ensure_active_member(user=user, couple=couple)
    try:
        resolved = resolve_topic_for_couple(couple=couple, topic_kind=topic_kind, topic_id=topic_id)
    except (Topic.DoesNotExist, CoupleTopic.DoesNotExist):
        raise ValidationError({"topic": "Topic is not available for this couple."}) from None

    session, created = TopicSession.objects.get_or_create(
        couple=couple,
        topic_kind=resolved.kind,
        topic_stable_key=resolved.stable_key,
        topic_version=resolved.version,
        defaults={
            "built_in_topic": resolved.built_in_topic,
            "custom_topic": resolved.custom_topic,
            "expected_question_count": resolved_question_count(resolved),
        },
    )
    if created and resolved.custom_topic is not None:
        mark_custom_topic_locked(resolved.custom_topic)
    if created:
        record_audit_event(action="topic_session.created", actor=user, target=session, request_id=request_id)
    return session


@transaction.atomic
def save_topic_answers(*, session: TopicSession, user: User, answers: list[dict], request_id: str = "") -> list[TopicResponse]:
    ensure_active_member(user=user, couple=session.couple)
    if TopicMemberCompletion.objects.filter(session=session, user=user).exists():
        raise ValidationError({"session": "Completed topic answers are locked."})
    if not answers:
        raise ValidationError({"answers": "At least one answer is required."})

    saved = []
    for answer in answers:
        question = resolve_question(session=session, question_id=answer.get("question_id"))
        selected_option_key = resolve_option_key(question=question, option_id=answer.get("selected_option_id"))
        response, _ = TopicResponse.objects.update_or_create(
            session=session,
            user=user,
            question_stable_key=question.stable_key,
            question_version=question.version,
            defaults={
                "couple": session.couple,
                "built_in_question": question if isinstance(question, Question) else None,
                "custom_question": question if isinstance(question, CustomQuestion) else None,
                "selected_option_key": selected_option_key,
                "text_answer": answer.get("text_answer", ""),
                "answered_at": timezone.now(),
            },
        )
        saved.append(response)

    record_audit_event(
        action="topic_answers.saved",
        actor=user,
        target=session,
        request_id=request_id,
        metadata={"answer_count": len(saved)},
    )
    return saved


@transaction.atomic
def complete_topic_session(*, session: TopicSession, user: User, answers: list[dict], request_id: str = "") -> TopicMemberCompletion:
    session = TopicSession.objects.select_for_update().get(id=session.id)
    save_topic_answers(session=session, user=user, answers=answers, request_id=request_id)
    expected_question_count = active_question_count(session)
    response_count = TopicResponse.objects.filter(session=session, user=user).count()
    if response_count < expected_question_count:
        raise ValidationError({"answers": f"Submit all {expected_question_count} answers before completing this topic."})

    now = timezone.now()
    completion, created = TopicMemberCompletion.objects.get_or_create(
        session=session,
        user=user,
        defaults={
            "couple": session.couple,
            "completed_at": now,
            "locked_at": now,
        },
    )
    if created:
        record_audit_event(action="topic_session.completed", actor=user, target=session, request_id=request_id)
        from apps.notifications.services import notify_topic_completed

        notify_topic_completed(completion=completion)
    synchronize_partner_completion(session=session, completion=completion, request_id=request_id)
    return completion


def session_is_released(session: TopicSession) -> bool:
    active_member_count = session.couple.members.filter(status=CoupleMember.Status.ACTIVE).count()
    if active_member_count < 2:
        return False
    return TopicMemberCompletion.objects.filter(session=session).count() >= active_member_count


def visible_responses_for_user(*, session: TopicSession, user: User):
    ensure_active_member(user=user, couple=session.couple)
    if session_is_released(session):
        return TopicResponse.objects.filter(session=session).select_related("user").order_by("user_id", "question_stable_key")
    return TopicResponse.objects.filter(session=session, user=user).order_by("question_stable_key")


def synchronize_partner_completion(
    *,
    session: TopicSession,
    completion: TopicMemberCompletion,
    request_id: str = "",
) -> TopicAnalysisJob | None:
    """
    Reconciles partner progress after a completion.

    This method is deliberately idempotent. Database uniqueness guarantees make it safe
    to call again from a retry, a worker, or a near-simultaneous partner completion path.
    """
    active_members = list(
        session.couple.members.filter(status=CoupleMember.Status.ACTIVE).select_related("user").order_by("role", "created_at")
    )
    active_user_ids = {member.user_id for member in active_members}
    completed_user_ids = set(
        TopicMemberCompletion.objects.filter(session=session, user_id__in=active_user_ids).values_list("user_id", flat=True)
    )

    if len(active_user_ids) < 2:
        return None

    if completed_user_ids < active_user_ids:
        waiting_user_ids = active_user_ids - completed_user_ids
        for user_id in waiting_user_ids:
            TopicSyncEvent.objects.get_or_create(
                session=session,
                user_id=user_id,
                event_type=TopicSyncEvent.EventType.PARTNER_COMPLETED_WAITING,
                defaults={
                    "couple": session.couple,
                    "metadata": {
                        "completed_user_id": str(completion.user_id),
                        "request_id": request_id,
                    },
                },
            )
        return None

    now = timezone.now()
    analysis_job, created = TopicAnalysisJob.objects.get_or_create(
        session=session,
        defaults={
            "couple": session.couple,
            "triggered_by_completion": completion,
            "status": TopicAnalysisJob.Status.QUEUED,
            "queued_at": now,
        },
    )
    for member in active_members:
        TopicSyncEvent.objects.get_or_create(
            session=session,
            user=member.user,
            event_type=TopicSyncEvent.EventType.ANALYSIS_QUEUED,
            defaults={
                "couple": session.couple,
                "metadata": {
                    "analysis_job_id": str(analysis_job.id),
                    "request_id": request_id,
                },
            },
        )
    if created:
        record_audit_event(
            action="topic_analysis.queued",
            actor=completion.user,
            target=session,
            request_id=request_id,
            metadata={"analysis_job_id": str(analysis_job.id)},
        )
        if settings.AI_AUTO_DISPATCH_ANALYSIS:
            from apps.ai.tasks import run_topic_analysis_task

            transaction.on_commit(lambda: run_topic_analysis_task.delay(str(analysis_job.id)))
    return analysis_job


@transaction.atomic
def mark_analysis_job_succeeded(*, analysis_job: TopicAnalysisJob, request_id: str = "") -> TopicAnalysisJob:
    analysis_job = TopicAnalysisJob.objects.select_for_update().select_related("session", "couple").get(id=analysis_job.id)
    if analysis_job.status != TopicAnalysisJob.Status.SUCCEEDED:
        analysis_job.status = TopicAnalysisJob.Status.SUCCEEDED
        analysis_job.finished_at = timezone.now()
        analysis_job.failure_reason = ""
        analysis_job.save(update_fields=["status", "finished_at", "failure_reason", "updated_at"])

    active_members = analysis_job.couple.members.filter(status=CoupleMember.Status.ACTIVE).select_related("user")
    for member in active_members:
        TopicSyncEvent.objects.get_or_create(
            session=analysis_job.session,
            user=member.user,
            event_type=TopicSyncEvent.EventType.ANALYSIS_READY,
            defaults={
                "couple": analysis_job.couple,
                "metadata": {
                    "analysis_job_id": str(analysis_job.id),
                    "request_id": request_id,
                },
            },
        )
    from apps.notifications.services import notify_analysis_ready

    notify_analysis_ready(analysis_job=analysis_job)
    return analysis_job


def sync_state_for_user(*, session: TopicSession, user: User) -> dict:
    ensure_active_member(user=user, couple=session.couple)
    active_user_ids = set(
        session.couple.members.filter(status=CoupleMember.Status.ACTIVE).values_list("user_id", flat=True)
    )
    completed_user_ids = set(
        TopicMemberCompletion.objects.filter(session=session, user_id__in=active_user_ids).values_list("user_id", flat=True)
    )
    try:
        analysis_job = session.analysis_job
    except TopicAnalysisJob.DoesNotExist:
        analysis_job = None
    current_user_completed = user.id in completed_user_ids
    all_active_members_completed = len(active_user_ids) >= 2 and completed_user_ids >= active_user_ids
    return {
        "expected_member_count": len(active_user_ids),
        "completed_member_count": len(completed_user_ids),
        "completed_user_ids": sorted(str(user_id) for user_id in completed_user_ids),
        "current_user_completed": current_user_completed,
        "waiting_for_partner": current_user_completed and not all_active_members_completed,
        "partner_is_waiting_for_you": not current_user_completed and bool(completed_user_ids),
        "is_released": all_active_members_completed,
        "analysis_job": None
        if analysis_job is None
        else {
            "id": str(analysis_job.id),
            "status": analysis_job.status,
            "queued_at": analysis_job.queued_at.isoformat() if analysis_job.queued_at else None,
            "finished_at": analysis_job.finished_at.isoformat() if analysis_job.finished_at else None,
        },
    }


def active_question_count(session: TopicSession) -> int:
    return session.expected_question_count


def resolved_question_count(resolved: ResolvedTopic) -> int:
    if resolved.kind == TopicSession.TopicKind.BUILT_IN:
        return Question.objects.filter(topic=resolved.built_in_topic, version=resolved.version, is_active=True).count()
    return CustomQuestion.objects.filter(topic=resolved.custom_topic, version=resolved.version, is_active=True).count()


def current_active_question_count(session: TopicSession) -> int:
    if session.topic_kind == TopicSession.TopicKind.BUILT_IN:
        return Question.objects.filter(topic=session.built_in_topic, version=session.topic_version, is_active=True).count()
    return CustomQuestion.objects.filter(topic=session.custom_topic, version=session.topic_version, is_active=True).count()


def resolve_question(*, session: TopicSession, question_id):
    if not question_id:
        raise ValidationError({"question_id": "Question id is required."})
    if session.topic_kind == TopicSession.TopicKind.BUILT_IN:
        try:
            return Question.objects.get(id=question_id, topic=session.built_in_topic, version=session.topic_version, is_active=True)
        except Question.DoesNotExist:
            raise ValidationError({"question_id": "Question is not part of this topic session."}) from None
    try:
        return CustomQuestion.objects.get(id=question_id, topic=session.custom_topic, version=session.topic_version, is_active=True)
    except CustomQuestion.DoesNotExist:
        raise ValidationError({"question_id": "Question is not part of this topic session."}) from None


def resolve_option_key(*, question, option_id) -> str:
    if not option_id:
        return ""
    if isinstance(question, Question):
        try:
            return QuestionOption.objects.get(id=option_id, question=question).stable_key
        except QuestionOption.DoesNotExist:
            raise ValidationError({"selected_option_id": "Option is not part of this question."}) from None
    try:
        return question.options.get(id=option_id).stable_key
    except CustomQuestionOption.DoesNotExist:
        raise ValidationError({"selected_option_id": "Option is not part of this question."}) from None
