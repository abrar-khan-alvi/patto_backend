from __future__ import annotations

import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from apps.ai.client import AIClientResponse, OpenAIResponsesClient
from apps.ai.exceptions import AIConfigurationError, AIProviderError
from apps.ai.models import AIPromptVersion
from apps.ai.policies import classify_safety_text
from apps.common.services import record_audit_event
from apps.couples.models import Couple
from apps.couples.permissions import user_is_active_couple_member
from apps.daily.models import DailyAnswer, DailyAssignment
from apps.insights.models import MonthlyInsight, MonthlyInsightInput
from apps.insights.schemas import MONTHLY_INSIGHT_JSON_SCHEMA, MonthlyInsightSchema


class MonthlyInsightClient(Protocol):
    def create_structured_response(
        self,
        *,
        model: str,
        input_messages: list[dict[str, str]],
        json_schema: dict,
        schema_name: str,
    ) -> AIClientResponse:
        ...


class MonthlyInsightNotClosed(Exception):
    pass


class MonthlyInsightAccessDenied(Exception):
    pass


@dataclass(frozen=True)
class MonthWindow:
    start: date
    end: date


def month_window(*, year: int, month: int) -> MonthWindow:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12.")
    return MonthWindow(start=date(year, month, 1), end=date(year, month, monthrange(year, month)[1]))


def active_monthly_insight_prompt() -> AIPromptVersion | None:
    return (
        AIPromptVersion.objects.filter(key=settings.AI_MONTHLY_INSIGHT_PROMPT_KEY, is_active=True)
        .order_by("-version")
        .first()
    )


def ensure_month_closed(*, window: MonthWindow, at=None) -> None:
    current_date = (at or timezone.now()).date()
    if current_date <= window.end:
        raise MonthlyInsightNotClosed("Monthly insights can only run after the target month closes.")


@transaction.atomic
def get_or_create_monthly_insight_job(*, couple: Couple, user, year: int, month: int, at=None) -> MonthlyInsight:
    if not user_is_active_couple_member(user, couple):
        raise MonthlyInsightAccessDenied("User is not an active member of this couple.")
    window = month_window(year=year, month=month)
    ensure_month_closed(window=window, at=at)
    insight, created = MonthlyInsight.objects.get_or_create(
        couple=couple,
        year=year,
        month=month,
        defaults={
            "input_start_date": window.start,
            "input_end_date": window.end,
            "minimum_revealed_days": settings.MONTHLY_INSIGHT_MIN_REVEALED_DAYS,
            "model": settings.OPENAI_MODEL,
            "queued_at": timezone.now(),
        },
    )
    if created:
        record_audit_event(
            actor=user,
            action="monthly_insight.queued",
            target=insight,
            metadata={"year": year, "month": month},
        )
    return insight


def eligible_revealed_assignments(*, couple: Couple, window: MonthWindow):
    return (
        DailyAssignment.objects.filter(
            couple=couple,
            status=DailyAssignment.Status.REVEALED,
            local_date__gte=window.start,
            local_date__lte=window.end,
        )
        .select_related("question")
        .order_by("local_date", "created_at")
    )


def collect_monthly_answers(*, couple: Couple, window: MonthWindow):
    return (
        DailyAnswer.objects.filter(
            couple=couple,
            assignment__status=DailyAssignment.Status.REVEALED,
            assignment__local_date__gte=window.start,
            assignment__local_date__lte=window.end,
        )
        .select_related("assignment", "assignment__question", "user")
        .order_by("assignment__local_date", "user_id")
    )


def build_monthly_insight_messages(*, insight: MonthlyInsight, prompt_version: AIPromptVersion) -> list[dict[str, str]]:
    answers = collect_monthly_answers(
        couple=insight.couple,
        window=MonthWindow(start=insight.input_start_date, end=insight.input_end_date),
    )
    answer_rows = [
        {
            "local_date": answer.assignment.local_date.isoformat(),
            "partner_id": str(answer.user_id),
            "question_key": answer.assignment.question.stable_key,
            "question_prompt": answer.assignment.question.prompt,
            "text_answer": answer.text_answer,
        }
        for answer in answers
    ]
    user_content = {
        "month": {"year": insight.year, "month": insight.month},
        "input_date_range": {
            "start": insight.input_start_date.isoformat(),
            "end": insight.input_end_date.isoformat(),
        },
        "daily_answers": answer_rows,
        "privacy_rule": "Use only revealed daily answers from this input date range.",
    }
    return [
        {"role": "system", "content": prompt_version.system_prompt},
        {"role": "developer", "content": prompt_version.developer_prompt},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
    ]


def monthly_insight_input_text(*, insight: MonthlyInsight) -> str:
    answers = collect_monthly_answers(
        couple=insight.couple,
        window=MonthWindow(start=insight.input_start_date, end=insight.input_end_date),
    )
    return "\n".join(answer.text_answer for answer in answers)


def usage_counts(usage: dict) -> tuple[int, int, int]:
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
    return int(input_tokens or 0), int(output_tokens or 0), int(total_tokens or 0)


@transaction.atomic
def persist_monthly_inputs(*, insight: MonthlyInsight) -> None:
    window = MonthWindow(start=insight.input_start_date, end=insight.input_end_date)
    answers = list(collect_monthly_answers(couple=insight.couple, window=window))
    MonthlyInsightInput.objects.filter(insight=insight).delete()
    for answer in answers:
        if not (window.start <= answer.assignment.local_date <= window.end):
            raise ValueError("Monthly insight input answer is outside the insight month.")
        MonthlyInsightInput.objects.create(
            insight=insight,
            assignment=answer.assignment,
            answer=answer,
            local_date=answer.assignment.local_date,
            user=answer.user,
            question_stable_key=answer.assignment.question.stable_key,
            question_prompt=answer.assignment.question.prompt,
            text_answer=answer.text_answer,
        )


@transaction.atomic
def mark_monthly_insight_ineligible(*, insight: MonthlyInsight, revealed_day_count: int, reason: str) -> MonthlyInsight:
    insight.status = MonthlyInsight.Status.INELIGIBLE
    insight.revealed_day_count = revealed_day_count
    insight.error_code = "minimum_participation_not_met"
    insight.error_message = reason
    insight.completed_at = timezone.now()
    insight.save(
        update_fields=[
            "status",
            "revealed_day_count",
            "error_code",
            "error_message",
            "completed_at",
            "updated_at",
        ]
    )
    return insight


@transaction.atomic
def persist_monthly_failure(
    *,
    insight: MonthlyInsight,
    prompt_version: AIPromptVersion | None,
    status: str,
    model: str,
    error_code: str = "",
    error_message: str = "",
    refusal_reason: str = "",
    usage: dict | None = None,
) -> MonthlyInsight:
    usage_data = usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    insight.prompt_version = prompt_version
    insight.status = status
    insight.model = model
    insight.usage = usage_data
    insight.input_tokens = input_tokens
    insight.output_tokens = output_tokens
    insight.total_tokens = total_tokens
    insight.error_code = error_code
    insight.error_message = error_message
    insight.refusal_reason = refusal_reason
    insight.completed_at = timezone.now()
    insight.save()
    return insight


@transaction.atomic
def persist_monthly_success(
    *,
    insight: MonthlyInsight,
    prompt_version: AIPromptVersion,
    provider_response: AIClientResponse,
    validated_output: MonthlyInsightSchema,
) -> MonthlyInsight:
    usage_data = provider_response.usage or {}
    input_tokens, output_tokens, total_tokens = usage_counts(usage_data)
    insight.prompt_version = prompt_version
    insight.status = MonthlyInsight.Status.SUCCEEDED
    insight.model = settings.OPENAI_MODEL
    insight.provider_response_id = provider_response.provider_response_id
    insight.sections = validated_output.model_dump()
    insight.safety_flags = validated_output.safety_flags
    insight.usage = usage_data
    insight.input_tokens = input_tokens
    insight.output_tokens = output_tokens
    insight.total_tokens = total_tokens
    insight.completed_at = timezone.now()
    insight.error_code = ""
    insight.error_message = ""
    insight.refusal_reason = ""
    insight.save()
    persist_monthly_inputs(insight=insight)
    record_audit_event(
        action="monthly_insight.succeeded",
        target=insight,
        metadata={"year": insight.year, "month": insight.month, "insight_id": str(insight.id)},
    )
    return insight


def run_monthly_insight(*, insight_id, client: MonthlyInsightClient | None = None, request_id: str = "") -> MonthlyInsight:
    with transaction.atomic():
        insight = MonthlyInsight.objects.select_for_update().select_related("couple").get(id=insight_id)
        if insight.status == MonthlyInsight.Status.SUCCEEDED:
            return insight
        insight.status = MonthlyInsight.Status.RUNNING
        insight.started_at = insight.started_at or timezone.now()
        insight.model = settings.OPENAI_MODEL
        insight.save(update_fields=["status", "started_at", "model", "updated_at"])

    window = MonthWindow(start=insight.input_start_date, end=insight.input_end_date)
    revealed_day_count = eligible_revealed_assignments(couple=insight.couple, window=window).count()
    insight.revealed_day_count = revealed_day_count
    insight.save(update_fields=["revealed_day_count", "updated_at"])
    if revealed_day_count < settings.MONTHLY_INSIGHT_MIN_REVEALED_DAYS:
        return mark_monthly_insight_ineligible(
            insight=insight,
            revealed_day_count=revealed_day_count,
            reason=f"At least {settings.MONTHLY_INSIGHT_MIN_REVEALED_DAYS} revealed daily questions are required.",
        )

    prompt_version = active_monthly_insight_prompt()
    if prompt_version is None:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=None,
            status=MonthlyInsight.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="missing_prompt_version",
            error_message="No active monthly insight prompt version is configured.",
        )

    input_text = monthly_insight_input_text(insight=insight)
    safety_decision = classify_safety_text(input_text)
    if safety_decision.is_restricted:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            error_code="safety_policy_blocked",
            error_message=f"AI safety policy routed input to {safety_decision.route.value}.",
        )

    try:
        resolved_client = client or OpenAIResponsesClient()
        provider_response = resolved_client.create_structured_response(
            model=settings.OPENAI_MODEL,
            input_messages=build_monthly_insight_messages(insight=insight, prompt_version=prompt_version),
            json_schema=prompt_version.output_schema or MONTHLY_INSIGHT_JSON_SCHEMA,
            schema_name="monthly_insight",
        )
    except AIConfigurationError as exc:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="configuration_error",
            error_message=str(exc),
        )
    except AIProviderError as exc:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.FAILED,
            model=settings.OPENAI_MODEL,
            error_code="provider_error",
            error_message=str(exc),
        )

    if provider_response.refusal_reason:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.REFUSED,
            model=settings.OPENAI_MODEL,
            refusal_reason=provider_response.refusal_reason,
            usage=provider_response.usage,
        )

    try:
        validated_output = MonthlyInsightSchema.model_validate(provider_response.content)
    except PydanticValidationError as exc:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.INVALID_OUTPUT,
            model=settings.OPENAI_MODEL,
            error_code="invalid_schema",
            error_message=str(exc),
            usage=provider_response.usage,
        )

    output_safety_decision = classify_safety_text(json.dumps(validated_output.model_dump(), ensure_ascii=False))
    if output_safety_decision.is_restricted:
        return persist_monthly_failure(
            insight=insight,
            prompt_version=prompt_version,
            status=MonthlyInsight.Status.SAFETY_BLOCKED,
            model=settings.OPENAI_MODEL,
            error_code="safety_policy_blocked_output",
            error_message=f"AI safety policy routed output to {output_safety_decision.route.value}.",
            usage=provider_response.usage,
        )

    return persist_monthly_success(
        insight=insight,
        prompt_version=prompt_version,
        provider_response=provider_response,
        validated_output=validated_output,
    )
