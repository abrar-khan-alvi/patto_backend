from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.services import record_audit_event
from apps.couples.models import Couple, CoupleMember
from apps.couples.permissions import user_is_active_couple_member
from apps.challenges.models import Challenge, ChallengeAssignment, ChallengeMemberCompletion
from apps.challenges.policies import validate_challenge_policy


class ChallengeUnavailable(Exception):
    pass


def active_member_count(couple: Couple) -> int:
    return CoupleMember.objects.filter(couple=couple, status=CoupleMember.Status.ACTIVE).count()


def safe_fallback_challenge() -> Challenge:
    challenge = (
        Challenge.objects.filter(is_active=True, source=Challenge.Source.FALLBACK)
        .order_by("sort_order", "stable_key")
        .first()
    )
    if challenge is None:
        challenge = Challenge.objects.filter(is_active=True).order_by("sort_order", "stable_key").first()
    if challenge is None:
        raise ChallengeUnavailable("No active challenges are configured.")
    return challenge


def ensure_active_member(*, user, couple: Couple) -> None:
    if not user_is_active_couple_member(user, couple):
        raise PermissionDenied("You must be an active couple member.")


@transaction.atomic
def assign_curated_challenge(*, couple: Couple, user, challenge: Challenge, starts_on=None, request_id: str = "") -> ChallengeAssignment:
    ensure_active_member(user=user, couple=couple)
    if not challenge.is_active:
        raise ValidationError({"challenge": "Challenge is not active."})
    starts = starts_on or timezone.localdate()
    assignment = ChallengeAssignment.objects.create(
        couple=couple,
        challenge=challenge,
        assigned_by=user,
        source=ChallengeAssignment.AssignmentSource.CURATED
        if challenge.source == Challenge.Source.CURATED
        else ChallengeAssignment.AssignmentSource.FALLBACK,
        starts_on=starts,
        due_on=starts + timedelta(days=max(challenge.duration_days, 1) - 1),
    )
    record_audit_event(action="challenge.assigned", actor=user, target=assignment, request_id=request_id)
    return assignment


@transaction.atomic
def assign_ai_suggested_challenge(
    *,
    couple: Couple,
    user,
    suggestion: dict | None,
    generation_failed: bool = False,
    request_id: str = "",
) -> ChallengeAssignment:
    ensure_active_member(user=user, couple=couple)
    starts = timezone.localdate()
    if generation_failed or not suggestion:
        fallback = safe_fallback_challenge()
        assignment = ChallengeAssignment.objects.create(
            couple=couple,
            challenge=fallback,
            assigned_by=user,
            source=ChallengeAssignment.AssignmentSource.FALLBACK,
            starts_on=starts,
            due_on=starts + timedelta(days=max(fallback.duration_days, 1) - 1),
            suggested_payload=suggestion or {},
            fallback_reason="generation_failed" if generation_failed else "missing_suggestion",
        )
        record_audit_event(action="challenge.fallback_assigned", actor=user, target=assignment, request_id=request_id)
        return assignment

    title = str(suggestion.get("title", "")).strip()
    description = str(suggestion.get("description", "")).strip()
    instructions = str(suggestion.get("instructions", "")).strip()
    decision = validate_challenge_policy(title=title, description=description, instructions=instructions)
    if not decision.allowed:
        raise ValidationError({"challenge": decision.reason, "safety_flags": decision.flags})

    challenge = Challenge.objects.create(
        stable_key=f"ai-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
        title=title,
        description=description,
        instructions=instructions,
        category=str(suggestion.get("category", "ai_suggested")).strip()[:80],
        source=Challenge.Source.AI_SUGGESTED,
        duration_days=int(suggestion.get("duration_days") or 1),
        safety_policy_version=decision.policy_version,
        is_active=False,
    )
    assignment = ChallengeAssignment.objects.create(
        couple=couple,
        challenge=challenge,
        assigned_by=user,
        source=ChallengeAssignment.AssignmentSource.AI_SUGGESTED,
        starts_on=starts,
        due_on=starts + timedelta(days=max(challenge.duration_days, 1) - 1),
        suggested_payload=suggestion,
        safety_flags=decision.flags,
    )
    record_audit_event(action="challenge.ai_suggested_assigned", actor=user, target=assignment, request_id=request_id)
    return assignment


@transaction.atomic
def complete_challenge_assignment(*, assignment: ChallengeAssignment, user, note: str = "", request_id: str = "") -> ChallengeMemberCompletion:
    assignment = ChallengeAssignment.objects.select_for_update().select_related("couple").get(id=assignment.id)
    ensure_active_member(user=user, couple=assignment.couple)
    if assignment.status == ChallengeAssignment.Status.CANCELED:
        raise ValidationError({"assignment": "Challenge assignment is canceled."})

    completion, created = ChallengeMemberCompletion.objects.get_or_create(
        assignment=assignment,
        user=user,
        defaults={
            "couple": assignment.couple,
            "note": note,
            "completed_at": timezone.now(),
        },
    )
    if created:
        record_audit_event(action="challenge.member_completed", actor=user, target=completion, request_id=request_id)

    if assignment.status != ChallengeAssignment.Status.COMPLETED:
        completed_count = assignment.member_completions.values("user_id").distinct().count()
        if completed_count >= active_member_count(assignment.couple):
            assignment.status = ChallengeAssignment.Status.COMPLETED
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=["status", "completed_at", "updated_at"])
    return completion
