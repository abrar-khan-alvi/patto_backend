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
from apps.ai.policies import SafetyRoute, classify_safety_text
from apps.common.services import record_audit_event
from apps.conflicts.models import ConflictBridge, ConflictMessage, ConflictMediation, ConflictPerspective, ConflictResolution, ConflictThread
from apps.conflicts.policies import bridge_avoids_blame
from apps.conflicts.schemas import CONFLICT_BRIDGE_JSON_SCHEMA, ConflictBridgeSchema
from apps.couples.models import Couple, CoupleMember
from apps.couples.permissions import user_is_active_couple_member


class ConflictBridgeClient(Protocol):
    def create_structured_response(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
        schema_name: str,
    ) -> AIClientResponse:
        ...


def active_conflict_bridge_prompt() -> AIPromptVersion | None:
    return (
        AIPromptVersion.objects.filter(key=settings.AI_CONFLICT_BRIDGE_PROMPT_KEY, is_active=True)
        .order_by("-version")
        .first()
    )


def active_members(couple: Couple):
    return couple.members.filter(status=CoupleMember.Status.ACTIVE).select_related("user").order_by("role", "created_at")


def ensure_conflict_member(*, user, thread: ConflictThread) -> None:
    if not user_is_active_couple_member(user, thread.couple):
        raise PermissionDenied("You must be an active couple member for this conflict.")


@transaction.atomic
def create_conflict_thread(*, user, title: str, request_id: str = "") -> ConflictThread:
    membership = user.couple_memberships.select_related("couple").filter(status=CoupleMember.Status.ACTIVE).first()
    if membership is None:
        raise ValidationError({"couple": "Join an active couple before starting conflict mode."})
    thread = ConflictThread.objects.create(couple=membership.couple, created_by=user, title=title.strip()[:180] or "Conflict")
    record_audit_event(action="conflict.created", actor=user, target=thread, request_id=request_id)
    return thread


@transaction.atomic
def submit_conflict_perspective(
    *,
    thread: ConflictThread,
    user,
    situation: str,
    feelings: str = "",
    needs: str = "",
    requested_outcome: str = "",
    lock: bool = False,
    request_id: str = "",
) -> ConflictPerspective:
    thread = ConflictThread.objects.select_for_update().select_related("couple").get(id=thread.id)
    ensure_conflict_member(user=user, thread=thread)
    if thread.status != ConflictThread.Status.COLLECTING:
        raise ValidationError({"thread": "Perspectives are locked for this conflict."})
    perspective, created = ConflictPerspective.objects.get_or_create(
        thread=thread,
        user=user,
        defaults={
            "couple": thread.couple,
            "situation": situation.strip(),
            "feelings": feelings.strip(),
            "needs": needs.strip(),
            "requested_outcome": requested_outcome.strip(),
        },
    )
    if not created:
        if perspective.locked_at is not None:
            raise ValidationError({"perspective": "Locked perspectives cannot be edited."})
        perspective.situation = situation.strip()
        perspective.feelings = feelings.strip()
        perspective.needs = needs.strip()
        perspective.requested_outcome = requested_outcome.strip()
    if not perspective.situation:
        raise ValidationError({"situation": "Situation is required."})
    if lock and perspective.locked_at is None:
        perspective.locked_at = timezone.now()
    perspective.save()
    maybe_mark_perspectives_locked(thread=thread)
    record_audit_event(action="conflict.perspective_submitted", actor=user, target=thread, request_id=request_id, metadata={"locked": bool(lock)})
    return perspective


@transaction.atomic
def maybe_mark_perspectives_locked(*, thread: ConflictThread) -> None:
    required = active_members(thread.couple).count()
    locked = ConflictPerspective.objects.filter(thread=thread, locked_at__isnull=False).values("user_id").distinct().count()
    if required >= 2 and locked >= required and thread.status == ConflictThread.Status.COLLECTING:
        thread.status = ConflictThread.Status.PERSPECTIVES_LOCKED
        thread.save(update_fields=["status", "updated_at"])


def visible_perspectives_for_user(*, thread: ConflictThread, user):
    ensure_conflict_member(user=user, thread=thread)
    return thread.perspectives.select_related("user").filter(user=user).order_by("created_at")


def build_conflict_bridge_messages(*, thread: ConflictThread, prompt_version: AIPromptVersion) -> list[dict[str, str]]:
    perspectives = thread.perspectives.select_related("user").order_by("user_id")
    rows = [
        {
            "partner_id": str(perspective.user_id),
            "situation": perspective.situation,
            "feelings": perspective.feelings,
            "needs": perspective.needs,
            "requested_outcome": perspective.requested_outcome,
        }
        for perspective in perspectives
    ]
    payload = {
        "conflict": {"id": str(thread.id), "title": thread.title},
        "private_perspectives": rows,
        "bridge_rule": (
            "Act as an AI conflict-support mediator with a therapist-like tone, while not claiming to be licensed therapy. "
            "Create a neutral bridge. Do not assign blame, decide who is right, or shame either partner."
        ),
    }
    return [
        {"role": "system", "content": prompt_version.system_prompt},
        {"role": "developer", "content": prompt_version.developer_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def usage_counts(usage: dict) -> tuple[int, int, int]:
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
    return int(input_tokens or 0), int(output_tokens or 0), int(total_tokens or 0)


@transaction.atomic
def persist_bridge_failure(
    *,
    thread: ConflictThread,
    prompt_version: AIPromptVersion | None,
    status: str,
    model: str,
    provider_response_id: str = "",
    usage: dict | None = None,
    refusal_reason: str = "",
    error_code: str = "",
    error_message: str = "",
    safety_flags: list[str] | None = None,
) -> ConflictBridge:
    usage_data = usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    bridge, _ = ConflictBridge.objects.update_or_create(
        thread=thread,
        defaults={
            "couple": thread.couple,
            "prompt_version": prompt_version,
            "status": status,
            "model": model,
            "provider_response_id": provider_response_id,
            "usage": usage_data,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "refusal_reason": refusal_reason,
            "error_code": error_code,
            "error_message": error_message,
            "safety_flags": safety_flags or [],
        },
    )
    return bridge


@transaction.atomic
def persist_bridge_success(
    *,
    thread: ConflictThread,
    prompt_version: AIPromptVersion,
    provider_response: AIClientResponse,
    validated_output: ConflictBridgeSchema,
) -> ConflictBridge:
    usage_data = provider_response.usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    bridge, _ = ConflictBridge.objects.update_or_create(
        thread=thread,
        defaults={
            "couple": thread.couple,
            "prompt_version": prompt_version,
            "status": ConflictBridge.Status.SUCCEEDED,
            "model": settings.OPENAI_MODEL,
            "provider_response_id": provider_response.provider_response_id,
            "neutral_summary": validated_output.neutral_summary,
            "partner_summaries": validated_output.partner_summaries,
            "common_ground": validated_output.common_ground,
            "next_steps": validated_output.next_steps,
            "safety_flags": validated_output.safety_flags,
            "usage": usage_data,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "refusal_reason": "",
            "error_code": "",
            "error_message": "",
        },
    )
    ConflictMessage.objects.get_or_create(
        thread=thread,
        sender_type=ConflictMessage.SenderType.AI,
        metadata={"bridge_id": str(bridge.id)},
        defaults={
            "couple": thread.couple,
            "author": None,
            "body": validated_output.neutral_summary,
            "render_as": "text",
        },
    )
    thread.status = ConflictThread.Status.DISCUSSION_OPEN
    thread.save(update_fields=["status", "updated_at"])
    record_audit_event(action="conflict.bridge_ready", actor=None, target=thread, metadata={"bridge_id": str(bridge.id)})
    return bridge


def run_conflict_bridge(*, thread: ConflictThread, user, client: ConflictBridgeClient | None = None, request_id: str = "") -> ConflictBridge:
    thread = ConflictThread.objects.select_related("couple").get(id=thread.id)
    ensure_conflict_member(user=user, thread=thread)
    if thread.status not in {ConflictThread.Status.PERSPECTIVES_LOCKED, ConflictThread.Status.BRIDGE_READY, ConflictThread.Status.DISCUSSION_OPEN}:
        raise ValidationError({"thread": "Both partners must lock private perspectives before generating a bridge."})
    existing = getattr(thread, "bridge", None)
    if existing is not None and existing.status == ConflictBridge.Status.SUCCEEDED:
        return existing

    prompt_version = active_conflict_bridge_prompt()
    if prompt_version is None:
        return persist_bridge_failure(thread=thread, prompt_version=None, status=ConflictBridge.Status.FAILED, model=settings.OPENAI_MODEL, error_code="missing_prompt_version", error_message="No active conflict bridge prompt version is configured.")

    input_messages = build_conflict_bridge_messages(thread=thread, prompt_version=prompt_version)
    input_text = "\n".join(message["content"] for message in input_messages)
    safety_decision = classify_safety_text(input_text)
    if safety_decision.route in {SafetyRoute.RESTRICTED_SAFETY, SafetyRoute.BLOCKED}:
        return persist_bridge_failure(
            thread=thread,
            prompt_version=prompt_version,
            status=ConflictBridge.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            error_code="safety_policy_blocked",
            error_message=f"AI safety policy routed input to {safety_decision.route.value}.",
            safety_flags=sorted({finding.category.value for finding in safety_decision.findings}),
        )
    try:
        resolved_client = client or OpenAIResponsesClient()
        provider_response = resolved_client.create_structured_response(
            model=settings.OPENAI_MODEL,
            input_messages=input_messages,
            json_schema=prompt_version.output_schema or CONFLICT_BRIDGE_JSON_SCHEMA,
            schema_name="conflict_bridge",
        )
    except AIConfigurationError as exc:
        return persist_bridge_failure(thread=thread, prompt_version=prompt_version, status=ConflictBridge.Status.FAILED, model=settings.OPENAI_MODEL, error_code="configuration_error", error_message=str(exc))
    except AIProviderError as exc:
        return persist_bridge_failure(thread=thread, prompt_version=prompt_version, status=ConflictBridge.Status.FAILED, model=settings.OPENAI_MODEL, error_code="provider_error", error_message=str(exc))
    if provider_response.refusal_reason:
        return persist_bridge_failure(thread=thread, prompt_version=prompt_version, status=ConflictBridge.Status.REFUSED, model=settings.OPENAI_MODEL, provider_response_id=provider_response.provider_response_id, usage=provider_response.usage, refusal_reason=provider_response.refusal_reason)
    try:
        validated_output = ConflictBridgeSchema.model_validate(provider_response.content)
    except PydanticValidationError as exc:
        return persist_bridge_failure(thread=thread, prompt_version=prompt_version, status=ConflictBridge.Status.INVALID_OUTPUT, model=settings.OPENAI_MODEL, provider_response_id=provider_response.provider_response_id, usage=provider_response.usage, error_code="invalid_schema", error_message=str(exc))
    if not bridge_avoids_blame(neutral_summary=validated_output.neutral_summary, partner_summaries=validated_output.partner_summaries, next_steps=validated_output.next_steps):
        return persist_bridge_failure(thread=thread, prompt_version=prompt_version, status=ConflictBridge.Status.POLICY_BLOCKED, model=settings.OPENAI_MODEL, provider_response_id=provider_response.provider_response_id, usage=provider_response.usage, error_code="bridge_blame_detected", error_message="Conflict bridge assigned blame or fault.")
    return persist_bridge_success(thread=thread, prompt_version=prompt_version, provider_response=provider_response, validated_output=validated_output)


@transaction.atomic
def add_conflict_message(*, thread: ConflictThread, user, body: str, request_id: str = "") -> ConflictMessage:
    thread = ConflictThread.objects.select_for_update().select_related("couple").get(id=thread.id)
    ensure_conflict_member(user=user, thread=thread)
    if thread.status not in {ConflictThread.Status.DISCUSSION_OPEN, ConflictThread.Status.RESOLVED}:
        raise ValidationError({"thread": "Shared discussion opens after the AI bridge is ready."})
    message = ConflictMessage.objects.create(thread=thread, couple=thread.couple, author=user, sender_type=ConflictMessage.SenderType.USER, body=body.strip(), render_as="text")
    record_audit_event(action="conflict.message_created", actor=user, target=thread, request_id=request_id)
    return message


@transaction.atomic
def request_conflict_mediation(*, thread: ConflictThread, user, prompt: str = "", request_id: str = "") -> ConflictMediation:
    thread = ConflictThread.objects.select_for_update().select_related("couple").get(id=thread.id)
    ensure_conflict_member(user=user, thread=thread)
    if thread.status not in {ConflictThread.Status.DISCUSSION_OPEN, ConflictThread.Status.RESOLVED}:
        raise ValidationError({"thread": "Mediation can be requested after the shared discussion opens."})
    mediation = ConflictMediation.objects.create(thread=thread, couple=thread.couple, requested_by=user, prompt=prompt.strip())
    record_audit_event(action="conflict.mediation_requested", actor=user, target=thread, request_id=request_id)
    return mediation


@transaction.atomic
def resolve_conflict(*, thread: ConflictThread, user, summary: str, proposed_pact_changes: list[str] | None = None, request_id: str = "") -> ConflictResolution:
    thread = ConflictThread.objects.select_for_update().select_related("couple").get(id=thread.id)
    ensure_conflict_member(user=user, thread=thread)
    if thread.status not in {ConflictThread.Status.DISCUSSION_OPEN, ConflictThread.Status.BRIDGE_READY}:
        raise ValidationError({"thread": "Conflict can be resolved after the shared bridge/discussion is open."})
    resolution, _ = ConflictResolution.objects.get_or_create(
        thread=thread,
        defaults={
            "couple": thread.couple,
            "resolved_by": user,
            "summary": summary.strip(),
            "proposed_pact_changes": [item.strip() for item in (proposed_pact_changes or []) if item.strip()],
        },
    )
    thread.status = ConflictThread.Status.RESOLVED
    thread.resolved_at = timezone.now()
    thread.save(update_fields=["status", "resolved_at", "updated_at"])
    record_audit_event(action="conflict.resolved", actor=user, target=thread, request_id=request_id)
    return resolution
