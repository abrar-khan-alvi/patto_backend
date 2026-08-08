import html

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.analysis.models import AnalysisRun
from apps.common.services import record_audit_event
from apps.couples.permissions import user_is_active_couple_member
from apps.discussions.models import DiscussionMessage, DiscussionThread, MediationRequest, MediationResponse
from apps.responses.models import TopicSession


def ensure_discussion_member(*, user, couple) -> None:
    if not user_is_active_couple_member(user, couple):
        raise PermissionDenied("Only active couple members can participate in this discussion.")


@transaction.atomic
def create_discussion_thread(*, user, session_id=None, analysis_run_id=None, title: str = "", request_id: str = "") -> DiscussionThread:
    if not session_id and not analysis_run_id:
        raise ValidationError({"session_id": "A session_id or analysis_run_id is required."})

    analysis_run = None
    session = None
    if analysis_run_id:
        analysis_run = AnalysisRun.objects.select_related("session", "couple").get(id=analysis_run_id)
        session = analysis_run.session
    elif session_id:
        session = TopicSession.objects.select_related("couple").get(id=session_id)

    ensure_discussion_member(user=user, couple=session.couple)
    thread = DiscussionThread.objects.create(
        couple=session.couple,
        session=session,
        analysis_run=analysis_run,
        title=title.strip()[:180],
        created_by=user,
    )
    record_audit_event(action="discussion_thread.created", actor=user, target=thread, request_id=request_id)
    return thread


@transaction.atomic
def create_discussion_message(*, thread: DiscussionThread, user, body: str, request_id: str = "") -> DiscussionMessage:
    ensure_discussion_member(user=user, couple=thread.couple)
    if thread.status != DiscussionThread.Status.OPEN:
        raise ValidationError({"thread": "Archived discussion threads cannot receive new messages."})
    normalized_body = sanitize_plain_text(body)
    if not normalized_body:
        raise ValidationError({"body": "Message body is required."})
    message = DiscussionMessage.objects.create(
        thread=thread,
        couple=thread.couple,
        author=user,
        sender_type=DiscussionMessage.SenderType.USER,
        body=normalized_body,
        metadata={"render_as": "text"},
    )
    record_audit_event(action="discussion_message.created", actor=user, target=thread, request_id=request_id)
    return message


@transaction.atomic
def request_mediation(*, thread: DiscussionThread, user, request_id: str = "") -> MediationRequest:
    ensure_discussion_member(user=user, couple=thread.couple)
    mediation_request = MediationRequest.objects.create(
        thread=thread,
        couple=thread.couple,
        requested_by=user,
        context_message_count=thread.messages.count(),
    )
    record_audit_event(action="discussion_mediation.requested", actor=user, target=thread, request_id=request_id)
    return mediation_request


@transaction.atomic
def record_mediation_failure(*, mediation_request: MediationRequest, failure_code: str, failure_message: str) -> MediationRequest:
    mediation_request.status = MediationRequest.Status.FAILED
    mediation_request.failure_code = failure_code[:80]
    mediation_request.failure_message = failure_message
    mediation_request.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])
    return mediation_request


@transaction.atomic
def record_mediation_success(*, mediation_request: MediationRequest, content: str, model: str = "", metadata: dict | None = None) -> MediationResponse:
    thread = mediation_request.thread
    body = sanitize_plain_text(content)
    if not body:
        raise ValidationError({"content": "Mediation content is required."})
    message = DiscussionMessage.objects.create(
        thread=thread,
        couple=thread.couple,
        author=None,
        sender_type=DiscussionMessage.SenderType.AI,
        body=body,
        metadata={"render_as": "text", "mediation_request_id": str(mediation_request.id)},
    )
    response = MediationResponse.objects.create(
        request=mediation_request,
        thread=thread,
        couple=thread.couple,
        message=message,
        content=body,
        model=model,
        metadata=metadata or {},
    )
    mediation_request.status = MediationRequest.Status.SUCCEEDED
    mediation_request.save(update_fields=["status", "updated_at"])
    return response


@transaction.atomic
def archive_discussion_thread(*, thread: DiscussionThread, user, request_id: str = "") -> DiscussionThread:
    ensure_discussion_member(user=user, couple=thread.couple)
    thread.status = DiscussionThread.Status.ARCHIVED
    thread.archived_at = timezone.now()
    thread.save(update_fields=["status", "archived_at", "updated_at"])
    record_audit_event(action="discussion_thread.archived", actor=user, target=thread, request_id=request_id)
    return thread


def sanitize_plain_text(value: str) -> str:
    return html.escape((value or "").strip(), quote=True)
