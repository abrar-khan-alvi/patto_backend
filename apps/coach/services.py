from __future__ import annotations

import json
from typing import Protocol

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.ai.client import AIClientResponse, OpenAIResponsesClient
from apps.ai.exceptions import AIConfigurationError, AIProviderError
from apps.ai.models import AIPromptVersion
from apps.ai.policies import SafetyRoute, classify_safety_text, restricted_safety_output
from apps.coach.models import CoachConversation, CoachMessage, CoachParticipant, CoachRun
from apps.coach.schemas import COACH_RESPONSE_JSON_SCHEMA, CoachResponseSchema
from apps.common.services import record_audit_event
from apps.couples.models import CoupleMember
from apps.couples.permissions import user_is_active_couple_member


class CoachClient(Protocol):
    def create_structured_response(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
        schema_name: str,
    ) -> AIClientResponse:
        ...


def active_coach_prompt() -> AIPromptVersion | None:
    return (
        AIPromptVersion.objects.filter(key=settings.AI_COACH_PROMPT_KEY, is_active=True)
        .order_by("-version")
        .first()
    )


def user_can_access_conversation(*, user, conversation: CoachConversation) -> bool:
    if conversation.scope == CoachConversation.Scope.INDIVIDUAL:
        return conversation.owner_id == user.id
    return CoachParticipant.objects.filter(conversation=conversation, user=user).exists() and user_is_active_couple_member(user, conversation.couple)


def ensure_conversation_access(*, user, conversation: CoachConversation) -> None:
    if not user_can_access_conversation(user=user, conversation=conversation):
        raise PermissionDenied("You cannot access this Coach conversation.")


@transaction.atomic
def create_coach_conversation(*, user, scope: str, title: str = "", request_id: str = "") -> CoachConversation:
    if scope not in CoachConversation.Scope.values:
        raise ValidationError({"scope": "Invalid Coach conversation scope."})
    membership = user.couple_memberships.select_related("couple").filter(status=CoupleMember.Status.ACTIVE).first()
    if scope in {CoachConversation.Scope.COUPLE, CoachConversation.Scope.CONFLICT} and membership is None:
        raise ValidationError({"couple": "Join an active couple before starting shared Coach conversations."})

    conversation = CoachConversation.objects.create(
        scope=scope,
        couple=membership.couple if membership is not None else None,
        owner=user,
        title=title.strip()[:180],
    )
    CoachParticipant.objects.create(conversation=conversation, user=user, role=CoachParticipant.Role.OWNER)
    if scope in {CoachConversation.Scope.COUPLE, CoachConversation.Scope.CONFLICT}:
        for member in membership.couple.members.filter(status=CoupleMember.Status.ACTIVE).exclude(user=user):
            CoachParticipant.objects.create(conversation=conversation, user=member.user, role=CoachParticipant.Role.PARTNER)
    record_audit_event(action="coach_conversation.created", actor=user, target=conversation, request_id=request_id)
    return conversation


@transaction.atomic
def add_coach_message(*, conversation: CoachConversation, user, body: str, request_id: str = "") -> CoachMessage:
    conversation = CoachConversation.objects.select_for_update().select_related("couple", "owner").get(id=conversation.id)
    ensure_conversation_access(user=user, conversation=conversation)
    normalized = body.strip()
    if not normalized:
        raise ValidationError({"body": "Message body is required."})
    message = CoachMessage.objects.create(
        conversation=conversation,
        couple=conversation.couple,
        author=user,
        sender_type=CoachMessage.SenderType.USER,
        body=normalized,
        render_as="text",
    )
    record_audit_event(action="coach_message.created", actor=user, target=conversation, request_id=request_id)
    return message


@transaction.atomic
def share_individual_coach_message(*, message: CoachMessage, user, request_id: str = "") -> CoachMessage:
    message = CoachMessage.objects.select_for_update().select_related("conversation", "conversation__owner").get(id=message.id)
    if message.conversation.scope != CoachConversation.Scope.INDIVIDUAL or message.author_id != user.id:
        raise PermissionDenied("Only the owner can share their individual Coach message.")
    if message.conversation.couple is None:
        membership = user.couple_memberships.select_related("couple").filter(status=CoupleMember.Status.ACTIVE).first()
        if membership is None:
            raise ValidationError({"couple": "Join an active couple before sharing Coach content."})
        message.conversation.couple = membership.couple
        message.conversation.save(update_fields=["couple", "updated_at"])
        message.couple = membership.couple
    message.explicitly_shared_with_partner = True
    message.shared_at = timezone.now()
    message.save(update_fields=["couple", "explicitly_shared_with_partner", "shared_at"])
    record_audit_event(action="coach_message.shared", actor=user, target=message.conversation, request_id=request_id)
    return message


def authorized_context_messages(*, conversation: CoachConversation, user) -> list[CoachMessage]:
    ensure_conversation_access(user=user, conversation=conversation)
    own_messages = list(conversation.messages.select_related("author").order_by("created_at"))
    if conversation.scope == CoachConversation.Scope.INDIVIDUAL:
        return [message for message in own_messages if message.author_id in {None, user.id} or message.sender_type == CoachMessage.SenderType.AI]
    shared_individual = list(
        CoachMessage.objects.filter(
            couple=conversation.couple,
            conversation__scope=CoachConversation.Scope.INDIVIDUAL,
            explicitly_shared_with_partner=True,
        )
        .select_related("author")
        .order_by("shared_at", "created_at")
    )
    return [*shared_individual, *own_messages]


def build_coach_messages(*, conversation: CoachConversation, user, prompt_version: AIPromptVersion) -> tuple[list[dict[str, str]], list[str]]:
    context_messages = authorized_context_messages(conversation=conversation, user=user)
    rows = [
        {
            "id": str(message.id),
            "scope": message.conversation.scope,
            "sender_type": message.sender_type,
            "author_id": str(message.author_id) if message.author_id else "",
            "explicitly_shared_with_partner": message.explicitly_shared_with_partner,
            "body": message.body,
        }
        for message in context_messages
    ]
    payload = {
        "conversation": {
            "id": str(conversation.id),
            "scope": conversation.scope,
            "privacy_rule": "Never include individual Coach content unless explicitly_shared_with_partner is true or this is the owner's individual conversation.",
        },
        "context_messages": rows,
    }
    return (
        [
            {"role": "system", "content": prompt_version.system_prompt},
            {"role": "developer", "content": prompt_version.developer_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        [str(message.id) for message in context_messages],
    )


def usage_counts(usage: dict) -> tuple[int, int, int]:
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
    return int(input_tokens or 0), int(output_tokens or 0), int(total_tokens or 0)


@transaction.atomic
def persist_coach_failure(
    *,
    conversation: CoachConversation,
    user,
    prompt_version: AIPromptVersion | None,
    status: str,
    model: str,
    context_message_ids: list[str] | None = None,
    provider_response_id: str = "",
    usage: dict | None = None,
    output: dict | None = None,
    safety_flags: list[str] | None = None,
    refusal_reason: str = "",
    error_code: str = "",
    error_message: str = "",
) -> CoachRun:
    usage_data = usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    return CoachRun.objects.create(
        conversation=conversation,
        couple=conversation.couple,
        requested_by=user,
        prompt_version=prompt_version,
        status=status,
        model=model,
        provider_response_id=provider_response_id,
        context_message_ids=context_message_ids or [],
        output=output or {},
        safety_flags=safety_flags or [],
        usage=usage_data,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        refusal_reason=refusal_reason,
        error_code=error_code,
        error_message=error_message,
    )


@transaction.atomic
def persist_coach_success(
    *,
    conversation: CoachConversation,
    user,
    prompt_version: AIPromptVersion,
    provider_response: AIClientResponse,
    validated_output: CoachResponseSchema,
    context_message_ids: list[str],
) -> CoachRun:
    usage_data = provider_response.usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    response_message = CoachMessage.objects.create(
        conversation=conversation,
        couple=conversation.couple,
        author=None,
        sender_type=CoachMessage.SenderType.AI,
        body=validated_output.message,
        render_as="text",
        metadata={"suggested_next_steps": validated_output.suggested_next_steps},
    )
    run = CoachRun.objects.create(
        conversation=conversation,
        couple=conversation.couple,
        requested_by=user,
        prompt_version=prompt_version,
        status=CoachRun.Status.SUCCEEDED,
        model=settings.OPENAI_MODEL,
        provider_response_id=provider_response.provider_response_id,
        response_message=response_message,
        context_message_ids=context_message_ids,
        output=validated_output.model_dump(),
        safety_flags=validated_output.safety_flags,
        usage=usage_data,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )
    record_audit_event(action="coach_run.succeeded", actor=user, target=conversation, metadata={"run_id": str(run.id)})
    return run


def run_coach(*, conversation: CoachConversation, user, client: CoachClient | None = None, request_id: str = "") -> CoachRun:
    conversation = CoachConversation.objects.select_related("couple", "owner").get(id=conversation.id)
    ensure_conversation_access(user=user, conversation=conversation)
    if conversation.scope != CoachConversation.Scope.INDIVIDUAL:
        raise ValidationError(
            {
                "scope": (
                    "AI Coach runs are only available for individual conversations. "
                    "Couple conversations are partner-to-partner chat without AI; use conflict mode for AI-assisted conflict support."
                )
            }
        )
    prompt_version = active_coach_prompt()
    if prompt_version is None:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=None,
            status=CoachRun.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="missing_prompt_version",
            error_message="No active Coach prompt version is configured.",
        )

    input_messages, context_message_ids = build_coach_messages(conversation=conversation, user=user, prompt_version=prompt_version)
    context_text = "\n".join(message["content"] for message in input_messages)
    input_safety_decision = classify_safety_text(context_text)
    if input_safety_decision.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            output=restricted_safety_output(input_safety_decision),
            safety_flags=sorted({finding.category.value for finding in input_safety_decision.findings}),
            error_code="safety_policy_blocked",
            error_message=f"AI safety policy routed input to {input_safety_decision.route.value}.",
        )

    try:
        resolved_client = client or OpenAIResponsesClient()
        provider_response = resolved_client.create_structured_response(
            model=settings.OPENAI_MODEL,
            input_messages=input_messages,
            json_schema=prompt_version.output_schema or COACH_RESPONSE_JSON_SCHEMA,
            schema_name="coach_response",
        )
    except AIConfigurationError as exc:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.FAILED,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            error_code="configuration_error",
            error_message=str(exc),
        )
    except AIProviderError as exc:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.FAILED,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            error_code="provider_error",
            error_message=str(exc),
        )

    if provider_response.refusal_reason:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.REFUSED,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage,
            refusal_reason=provider_response.refusal_reason,
        )

    try:
        validated_output = CoachResponseSchema.model_validate(provider_response.content)
    except PydanticValidationError as exc:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.INVALID_OUTPUT,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage,
            error_code="invalid_schema",
            error_message=str(exc),
        )

    output_safety_decision = classify_safety_text(validated_output.message)
    if output_safety_decision.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}:
        return persist_coach_failure(
            conversation=conversation,
            user=user,
            prompt_version=prompt_version,
            status=CoachRun.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            context_message_ids=context_message_ids,
            provider_response_id=provider_response.provider_response_id,
            usage=provider_response.usage,
            safety_flags=sorted({finding.category.value for finding in output_safety_decision.findings}),
            error_code="safety_policy_blocked_output",
            error_message=f"AI safety policy routed output to {output_safety_decision.route.value}.",
        )

    return persist_coach_success(
        conversation=conversation,
        user=user,
        prompt_version=prompt_version,
        provider_response=provider_response,
        validated_output=validated_output,
        context_message_ids=context_message_ids,
    )
