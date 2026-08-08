from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from apps.couples.models import Couple, CoupleMember
from apps.couples.permissions import user_is_active_couple_member
from apps.daily.models import CoupleStreak, DailyAnswer, DailyAssignment, DailyQuestion, DailyReveal


class DailyQuestionUnavailable(Exception):
    pass


class DailyAccessDenied(Exception):
    pass


class DailyAlreadyRevealed(Exception):
    pass


def safe_zoneinfo(timezone_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def active_member_count(couple: Couple) -> int:
    return CoupleMember.objects.filter(couple=couple, status=CoupleMember.Status.ACTIVE).count()


def local_date_for_user(*, user, at: datetime | None = None):
    current_time = at or timezone.now()
    if timezone.is_naive(current_time):
        current_time = timezone.make_aware(current_time, timezone=UTC)
    return current_time.astimezone(safe_zoneinfo(getattr(user, "timezone", "UTC"))).date()


def select_daily_question(*, local_date) -> DailyQuestion:
    questions = list(DailyQuestion.objects.filter(is_active=True).order_by("sort_order", "stable_key"))
    if not questions:
        raise DailyQuestionUnavailable("No active daily questions are configured.")
    epoch = datetime(2026, 1, 1, tzinfo=UTC).date()
    index = (local_date - epoch).days % len(questions)
    return questions[index]


@transaction.atomic
def get_or_create_daily_assignment(*, couple: Couple, user, at: datetime | None = None) -> DailyAssignment:
    if not user_is_active_couple_member(user, couple):
        raise DailyAccessDenied("User is not an active member of this couple.")

    local_date = local_date_for_user(user=user, at=at)
    question = select_daily_question(local_date=local_date)
    assignment, _ = DailyAssignment.objects.select_for_update().get_or_create(
        couple=couple,
        local_date=local_date,
        defaults={
            "question": question,
            "timezone": getattr(user, "timezone", "UTC") or "UTC",
        },
    )
    return assignment


def visible_daily_answers_for_user(*, assignment: DailyAssignment, user):
    answers = assignment.answers.select_related("user").order_by("answered_at", "created_at")
    if assignment.status == DailyAssignment.Status.REVEALED or hasattr(assignment, "reveal"):
        return answers
    return answers.filter(user=user)


def daily_assignment_is_revealed(assignment: DailyAssignment) -> bool:
    return assignment.status == DailyAssignment.Status.REVEALED or hasattr(assignment, "reveal")


def update_streak_for_reveal(*, couple: Couple, local_date) -> CoupleStreak:
    streak, _ = CoupleStreak.objects.select_for_update().get_or_create(couple=couple)
    if streak.last_completed_date == local_date:
        return streak
    if streak.last_completed_date == local_date - timedelta(days=1):
        streak.current_count += 1
    else:
        streak.current_count = 1
    streak.longest_count = max(streak.longest_count, streak.current_count)
    streak.last_completed_date = local_date
    streak.save(update_fields=["current_count", "longest_count", "last_completed_date", "updated_at"])
    return streak


def maybe_reveal_assignment(*, assignment: DailyAssignment) -> DailyReveal | None:
    required_count = active_member_count(assignment.couple)
    answered_count = assignment.answers.values("user_id").distinct().count()
    if required_count < 2 or answered_count < required_count:
        return None

    reveal, _ = DailyReveal.objects.get_or_create(
        assignment=assignment,
        defaults={
            "couple": assignment.couple,
            "revealed_at": timezone.now(),
        },
    )
    if assignment.status != DailyAssignment.Status.REVEALED:
        assignment.status = DailyAssignment.Status.REVEALED
        assignment.save(update_fields=["status", "updated_at"])
    update_streak_for_reveal(couple=assignment.couple, local_date=assignment.local_date)
    return reveal


@transaction.atomic
def submit_daily_answer(*, assignment: DailyAssignment, user, text_answer: str) -> DailyAnswer:
    assignment = DailyAssignment.objects.select_for_update().select_related("couple").get(id=assignment.id)
    if not user_is_active_couple_member(user, assignment.couple):
        raise DailyAccessDenied("User is not an active member of this couple.")
    if daily_assignment_is_revealed(assignment):
        raise DailyAlreadyRevealed("Daily answers are locked after reveal.")

    answer, created = DailyAnswer.objects.get_or_create(
        assignment=assignment,
        user=user,
        defaults={
            "couple": assignment.couple,
            "text_answer": text_answer,
            "answered_at": timezone.now(),
        },
    )
    if created:
        maybe_reveal_assignment(assignment=assignment)
    return answer


def streak_for_couple(couple: Couple) -> CoupleStreak:
    streak, _ = CoupleStreak.objects.get_or_create(couple=couple)
    return streak
