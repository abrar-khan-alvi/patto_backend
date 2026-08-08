import json
from typing import Protocol

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from apps.ai.client import AIClientResponse, OpenAIResponsesClient
from apps.ai.exceptions import AIConfigurationError, AIProviderError
from apps.ai.models import AIAnalysisResult, AIFollowUpQuestion, AIPromptVersion
from apps.ai.policies import (
    SafetyRoute,
    classify_safety_text,
    record_safety_decision,
    restricted_safety_output,
)
from apps.ai.schemas import (
    FOLLOW_UP_QUESTION_JSON_SCHEMA,
    TOPIC_ANALYSIS_JSON_SCHEMA,
    FollowUpQuestionSchema,
    TopicAnalysisSchema,
)
from apps.common.services import record_audit_event
from apps.responses.models import TopicAnalysisJob, TopicResponse
from apps.responses.services import mark_analysis_job_succeeded


class TopicAnalysisClient(Protocol):
    def create_topic_analysis(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
    ) -> AIClientResponse:
        ...


class FollowUpQuestionClient(Protocol):
    def create_follow_up_question(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
    ) -> AIClientResponse:
        ...


def active_topic_analysis_prompt() -> AIPromptVersion:
    return (
        AIPromptVersion.objects.filter(key=settings.AI_TOPIC_ANALYSIS_PROMPT_KEY, is_active=True)
        .order_by("-version")
        .first()
    )


def active_follow_up_prompt() -> AIPromptVersion:
    return (
        AIPromptVersion.objects.filter(key=settings.AI_FOLLOW_UP_PROMPT_KEY, is_active=True)
        .order_by("-version")
        .first()
    )


def build_topic_analysis_messages(*, analysis_job: TopicAnalysisJob, prompt_version: AIPromptVersion) -> list[dict[str, str]]:
    session = analysis_job.session
    responses = (
        TopicResponse.objects.filter(session=session)
        .select_related("user")
        .order_by("user_id", "question_stable_key")
    )
    answer_lines = []
    for response in responses:
        answer_lines.append(
            {
                "partner_id": str(response.user_id),
                "question_key": response.question_stable_key,
                "question_version": response.question_version,
                "selected_option_key": response.selected_option_key,
                "text_answer": response.text_answer,
            }
        )
    user_content = {
        "topic": {
            "kind": session.topic_kind,
            "stable_key": session.topic_stable_key,
            "version": session.topic_version,
        },
        "responses": answer_lines,
    }
    return [
        {"role": "system", "content": prompt_version.system_prompt},
        {"role": "developer", "content": prompt_version.developer_prompt},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
    ]


def build_follow_up_messages(*, session, user, prompt_version: AIPromptVersion) -> list[dict[str, str]]:
    responses = TopicResponse.objects.filter(session=session, user=user).order_by("question_stable_key")
    answer_lines = []
    for response in responses:
        answer_lines.append(
            {
                "question_key": response.question_stable_key,
                "question_version": response.question_version,
                "selected_option_key": response.selected_option_key,
                "text_answer": response.text_answer,
            }
        )
    user_content = {
        "topic": {
            "kind": session.topic_kind,
            "stable_key": session.topic_stable_key,
            "version": session.topic_version,
        },
        "user": {
            "id": str(user.id),
            "preferred_language": user.preferred_language,
        },
        "current_user_answers_only": answer_lines,
        "privacy_rule": "Do not use or infer the partner's private answers.",
    }
    return [
        {"role": "system", "content": prompt_version.system_prompt},
        {"role": "developer", "content": prompt_version.developer_prompt},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
    ]


def generate_follow_up_question(
    *,
    session,
    user,
    client: FollowUpQuestionClient | None = None,
    request_id: str = "",
) -> AIFollowUpQuestion:
    from apps.responses.services import ensure_active_member

    ensure_active_member(user=user, couple=session.couple)
    existing = AIFollowUpQuestion.objects.filter(session=session, user=user).first()
    if existing is not None:
        return existing

    prompt_version = active_follow_up_prompt()
    if prompt_version is None:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=None,
            status=AIFollowUpQuestion.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="missing_prompt_version",
            error_message="No active follow-up prompt version is configured.",
        )

    own_answer_text = follow_up_input_text(session=session, user=user)
    if not own_answer_text:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.SKIPPED,
            model=settings.OPENAI_MODEL,
            skip=True,
            skip_reason="No current-user answers are available for follow-up generation.",
        )

    input_safety_decision = classify_safety_text(own_answer_text)
    if input_safety_decision.is_restricted:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            skip=True,
            skip_reason="Follow-up generation was restricted by AI safety policy.",
            error_code="safety_policy_blocked",
            error_message=f"AI safety policy routed input to {input_safety_decision.route.value}.",
        )

    resolved_client = client
    try:
        if resolved_client is None:
            resolved_client = OpenAIResponsesClient()
        provider_response = resolved_client.create_follow_up_question(
            model=settings.OPENAI_MODEL,
            input_messages=build_follow_up_messages(session=session, user=user, prompt_version=prompt_version),
            json_schema=prompt_version.output_schema or FOLLOW_UP_QUESTION_JSON_SCHEMA,
        )
    except AIConfigurationError as exc:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="configuration_error",
            error_message=str(exc),
        )
    except AIProviderError as exc:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="provider_error",
            error_message=str(exc),
        )

    if provider_response.refusal_reason:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.REFUSED,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            refusal_reason=provider_response.refusal_reason,
        )

    try:
        validated_output = FollowUpQuestionSchema.model_validate(provider_response.content)
    except PydanticValidationError as exc:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.INVALID_OUTPUT,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            error_code="invalid_output",
            error_message=str(exc),
        )
    if validated_output.topic_stable_key != session.topic_stable_key or validated_output.topic_version != session.topic_version:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.INVALID_OUTPUT,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            error_code="topic_mismatch",
            error_message="Follow-up output did not match the frozen topic session.",
        )

    output_safety_decision = classify_safety_text(
        "\n".join([validated_output.follow_up_question, validated_output.skip_reason])
    )
    if output_safety_decision.is_restricted:
        return persist_follow_up_failure(
            session=session,
            user=user,
            prompt_version=prompt_version,
            status=AIFollowUpQuestion.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            skip=True,
            skip_reason="Generated follow-up was blocked by AI safety policy.",
            error_code="safety_policy_blocked",
            error_message=f"AI safety policy routed output to {output_safety_decision.route.value}.",
        )

    usage = provider_response.usage or {}
    status = AIFollowUpQuestion.Status.SKIPPED if validated_output.skip else AIFollowUpQuestion.Status.SUCCEEDED
    follow_up, _ = AIFollowUpQuestion.objects.get_or_create(
        session=session,
        user=user,
        defaults={
            "couple": session.couple,
            "prompt_version": prompt_version,
            "status": status,
            "model": settings.OPENAI_MODEL,
            "provider_response_id": provider_response.provider_response_id,
            "topic_stable_key": validated_output.topic_stable_key,
            "topic_version": validated_output.topic_version,
            "follow_up_question": validated_output.follow_up_question,
            "internal_reason": validated_output.internal_reason,
            "skip": validated_output.skip,
            "skip_reason": validated_output.skip_reason,
            "usage": usage,
            "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0,
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0,
            "total_tokens": usage.get("total_tokens", 0) or 0,
        },
    )
    record_audit_event(
        action="ai_follow_up.generated",
        actor=user,
        target=session,
        request_id=request_id,
        metadata={"follow_up_id": str(follow_up.id), "status": follow_up.status},
    )
    return follow_up


def follow_up_input_text(*, session, user) -> str:
    responses = TopicResponse.objects.filter(session=session, user=user).order_by("question_stable_key")
    return "\n".join(response.text_answer for response in responses if response.text_answer)


def persist_follow_up_failure(
    *,
    session,
    user,
    prompt_version: AIPromptVersion | None,
    status: str,
    model: str,
    provider_response_id: str = "",
    usage: dict | None = None,
    refusal_reason: str = "",
    error_code: str = "",
    error_message: str = "",
    skip: bool = False,
    skip_reason: str = "",
) -> AIFollowUpQuestion:
    usage = usage or {}
    follow_up, _ = AIFollowUpQuestion.objects.get_or_create(
        session=session,
        user=user,
        defaults={
            "couple": session.couple,
            "prompt_version": prompt_version,
            "status": status,
            "model": model,
            "provider_response_id": provider_response_id,
            "topic_stable_key": session.topic_stable_key,
            "topic_version": session.topic_version,
            "skip": skip,
            "skip_reason": skip_reason,
            "usage": usage,
            "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0,
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0,
            "total_tokens": usage.get("total_tokens", 0) or 0,
            "refusal_reason": refusal_reason,
            "error_code": error_code,
            "error_message": error_message,
        },
    )
    return follow_up


def run_topic_analysis(*, analysis_job_id, client: TopicAnalysisClient | None = None, request_id: str = "") -> AIAnalysisResult:
    with transaction.atomic():
        analysis_job = (
            TopicAnalysisJob.objects.select_for_update()
            .select_related("session", "couple")
            .get(id=analysis_job_id)
        )
        existing_result = getattr(analysis_job, "ai_result", None)
        if existing_result and existing_result.status == AIAnalysisResult.Status.SUCCEEDED:
            return existing_result

        prompt_version = active_topic_analysis_prompt()
        if prompt_version is None:
            return fail_analysis_job(
                analysis_job=analysis_job,
                status=AIAnalysisResult.Status.FAILED,
                model=settings.OPENAI_MODEL,
                error_code="missing_prompt_version",
                error_message="No active topic analysis prompt version is configured.",
            )

        analysis_job.status = TopicAnalysisJob.Status.RUNNING
        analysis_job.started_at = analysis_job.started_at or timezone.now()
        analysis_job.failure_reason = ""
        analysis_job.save(update_fields=["status", "started_at", "failure_reason", "updated_at"])

    input_safety_decision = classify_safety_text(analysis_input_text(analysis_job=analysis_job))
    if input_safety_decision.findings:
        record_safety_decision(
            analysis_job=analysis_job,
            stage="input",
            decision=input_safety_decision,
        )
    if input_safety_decision.is_restricted:
        return safety_block_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            stage="input",
            decision=input_safety_decision,
            model=settings.OPENAI_MODEL,
        )

    resolved_client = client
    try:
        if resolved_client is None:
            resolved_client = OpenAIResponsesClient()
        provider_response = resolved_client.create_topic_analysis(
            model=settings.OPENAI_MODEL,
            input_messages=build_topic_analysis_messages(analysis_job=analysis_job, prompt_version=prompt_version),
            json_schema=prompt_version.output_schema or TOPIC_ANALYSIS_JSON_SCHEMA,
        )
    except AIConfigurationError as exc:
        return fail_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            status=AIAnalysisResult.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="configuration_error",
            error_message=str(exc),
        )
    except AIProviderError as exc:
        return fail_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            status=AIAnalysisResult.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="provider_error",
            error_message=str(exc),
        )

    if provider_response.refusal_reason:
        return fail_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            status=AIAnalysisResult.Status.REFUSED,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            refusal_reason=provider_response.refusal_reason,
        )

    try:
        validated_output = TopicAnalysisSchema.model_validate(provider_response.content).model_dump()
    except PydanticValidationError as exc:
        return fail_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            status=AIAnalysisResult.Status.INVALID_OUTPUT,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
            error_code="invalid_output",
            error_message=str(exc),
        )

    output_safety_decision = classify_safety_text(analysis_output_text(validated_output))
    if output_safety_decision.findings:
        record_safety_decision(
            analysis_job=analysis_job,
            stage="output",
            decision=output_safety_decision,
        )
    if output_safety_decision.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}:
        return safety_block_analysis_job(
            analysis_job=analysis_job,
            prompt_version=prompt_version,
            stage="output",
            decision=output_safety_decision,
            model=settings.OPENAI_MODEL,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage or {},
        )

    usage = provider_response.usage or {}
    result, _ = AIAnalysisResult.objects.update_or_create(
        analysis_job=analysis_job,
        defaults={
            "prompt_version": prompt_version,
            "status": AIAnalysisResult.Status.SUCCEEDED,
            "model": settings.OPENAI_MODEL,
            "provider_response_id": provider_response.provider_response_id,
            "output": validated_output,
            "usage": usage,
            "input_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0,
            "output_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0,
            "total_tokens": usage.get("total_tokens", 0) or 0,
            "refusal_reason": "",
            "error_code": "",
            "error_message": "",
        },
    )
    mark_analysis_job_succeeded(analysis_job=analysis_job, request_id=request_id)
    from apps.analysis.services import materialize_topic_analysis

    materialize_topic_analysis(ai_result=result, request_id=request_id)
    record_audit_event(
        action="topic_analysis.succeeded",
        actor=None,
        target=analysis_job.session,
        request_id=request_id,
        metadata={"analysis_job_id": str(analysis_job.id), "ai_result_id": str(result.id)},
    )
    return result


def analysis_input_text(*, analysis_job: TopicAnalysisJob) -> str:
    responses = TopicResponse.objects.filter(session=analysis_job.session).order_by("user_id", "question_stable_key")
    return "\n".join(response.text_answer for response in responses if response.text_answer)


def analysis_output_text(output: dict) -> str:
    values = [
        output.get("relationship_summary", ""),
        *output.get("strengths", []),
        *output.get("growth_areas", []),
        *output.get("conversation_starters", []),
        *output.get("suggested_pact_items", []),
        *output.get("safety_notes", []),
    ]
    return "\n".join(str(value) for value in values if value)


def safety_block_analysis_job(
    *,
    analysis_job: TopicAnalysisJob,
    prompt_version: AIPromptVersion | None,
    stage: str,
    decision,
    model: str,
    provider_response_id: str = "",
    usage: dict | None = None,
) -> AIAnalysisResult:
    analysis_job.status = TopicAnalysisJob.Status.FAILED
    analysis_job.finished_at = timezone.now()
    analysis_job.failure_reason = f"AI safety policy routed {stage} to {decision.route.value}."
    analysis_job.save(update_fields=["status", "finished_at", "failure_reason", "updated_at"])
    result, _ = AIAnalysisResult.objects.update_or_create(
        analysis_job=analysis_job,
        defaults={
            "prompt_version": prompt_version,
            "status": AIAnalysisResult.Status.SAFETY_BLOCKED,
            "model": model,
            "provider_response_id": provider_response_id,
            "output": restricted_safety_output(decision),
            "usage": usage or {},
            "input_tokens": (usage or {}).get("input_tokens", (usage or {}).get("prompt_tokens", 0)) or 0,
            "output_tokens": (usage or {}).get("output_tokens", (usage or {}).get("completion_tokens", 0)) or 0,
            "total_tokens": (usage or {}).get("total_tokens", 0) or 0,
            "refusal_reason": "",
            "error_code": "safety_policy_blocked",
            "error_message": analysis_job.failure_reason,
        },
    )
    record_audit_event(
        action="topic_analysis.safety_blocked",
        actor=None,
        target=analysis_job.session,
        metadata={
            "analysis_job_id": str(analysis_job.id),
            "stage": stage,
            "route": decision.route.value,
            "highest_severity": decision.highest_severity.value,
            "categories": sorted({finding.category.value for finding in decision.findings}),
            "raw_text_retained": False,
        },
    )
    return result


def fail_analysis_job(
    *,
    analysis_job: TopicAnalysisJob,
    status: str,
    model: str,
    prompt_version: AIPromptVersion | None = None,
    provider_response_id: str = "",
    usage: dict | None = None,
    refusal_reason: str = "",
    error_code: str = "",
    error_message: str = "",
) -> AIAnalysisResult:
    analysis_job.status = TopicAnalysisJob.Status.FAILED
    analysis_job.finished_at = timezone.now()
    analysis_job.failure_reason = refusal_reason or error_message
    analysis_job.save(update_fields=["status", "finished_at", "failure_reason", "updated_at"])
    result, _ = AIAnalysisResult.objects.update_or_create(
        analysis_job=analysis_job,
        defaults={
            "prompt_version": prompt_version,
            "status": status,
            "model": model,
            "provider_response_id": provider_response_id,
            "output": None,
            "usage": usage or {},
            "input_tokens": (usage or {}).get("input_tokens", (usage or {}).get("prompt_tokens", 0)) or 0,
            "output_tokens": (usage or {}).get("output_tokens", (usage or {}).get("completion_tokens", 0)) or 0,
            "total_tokens": (usage or {}).get("total_tokens", 0) or 0,
            "refusal_reason": refusal_reason,
            "error_code": error_code,
            "error_message": error_message,
        },
    )
    return result
