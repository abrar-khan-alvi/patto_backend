from datetime import UTC, datetime

import pytest
from django.test import override_settings

from apps.accounts.models import User
from apps.daily.models import CoupleStreak, DailyAnswer, DailyAssignment, DailyReveal
from apps.daily.services import get_or_create_daily_assignment, submit_daily_answer
from tests.helpers import authenticated_client


def create_active_couple():
    partner_one = authenticated_client("daily-p1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "daily-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client("daily-p2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_current_daily_assignment_is_unique_for_couple_and_local_date():
    partner_one, partner_two = create_active_couple()

    first = partner_one.get("/api/v1/daily/current/")
    second = partner_two.get("/api/v1/daily/current/")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["assignment"]["id"] == second.json()["assignment"]["id"]
    assert DailyAssignment.objects.count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_one_answer_per_user_per_daily_assignment():
    partner_one, _ = create_active_couple()
    assignment_id = partner_one.get("/api/v1/daily/current/").json()["assignment"]["id"]

    first = partner_one.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "I need a calm evening."},
        content_type="application/json",
    )
    second = partner_one.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "Trying to answer twice."},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert DailyAnswer.objects.count() == 1
    assert DailyAnswer.objects.get().text_answer == "I need a calm evening."


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_answers_are_private_until_both_partners_answer():
    partner_one, partner_two = create_active_couple()
    assignment_id = partner_one.get("/api/v1/daily/current/").json()["assignment"]["id"]

    partner_one.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "I would like help with dinner."},
        content_type="application/json",
    )

    one_view = partner_one.get(f"/api/v1/daily/{assignment_id}/").json()
    two_view = partner_two.get(f"/api/v1/daily/{assignment_id}/").json()

    assert len(one_view["answers"]) == 1
    assert one_view["answers"][0]["text_answer"] == "I would like help with dinner."
    assert two_view["answers"] == []
    assert one_view["assignment"]["is_revealed"] is False


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_daily_reveals_after_both_partners_answer_and_updates_streak():
    partner_one, partner_two = create_active_couple()
    assignment_id = partner_one.get("/api/v1/daily/current/").json()["assignment"]["id"]

    partner_one.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "I appreciate your patience."},
        content_type="application/json",
    )
    response = partner_two.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "I appreciate your humor."},
        content_type="application/json",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["assignment"]["is_revealed"] is True
    assert len(body["answers"]) == 2
    assert DailyReveal.objects.count() == 1
    assert CoupleStreak.objects.get().current_count == 1
    assert CoupleStreak.objects.get().longest_count == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_daily_assignment_uses_user_timezone_boundary():
    partner_one, _ = create_active_couple()
    user = User.objects.get(email="daily-p1@example.com")
    user.timezone = "Asia/Dhaka"
    user.save(update_fields=["timezone", "updated_at"])
    membership = user.couple_memberships.select_related("couple").get()

    assignment = get_or_create_daily_assignment(
        couple=membership.couple,
        user=user,
        at=datetime(2026, 8, 8, 18, 30, tzinfo=UTC),
    )

    assert assignment.local_date.isoformat() == "2026-08-09"
    assert assignment.timezone == "Asia/Dhaka"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_missed_days_reset_streak_and_consecutive_days_increment():
    create_active_couple()
    p1 = User.objects.get(email="daily-p1@example.com")
    p2 = User.objects.get(email="daily-p2@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple

    day_one = get_or_create_daily_assignment(
        couple=couple,
        user=p1,
        at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )
    submit_daily_answer(assignment=day_one, user=p1, text_answer="day one p1")
    submit_daily_answer(assignment=day_one, user=p2, text_answer="day one p2")
    assert CoupleStreak.objects.get(couple=couple).current_count == 1

    day_three = get_or_create_daily_assignment(
        couple=couple,
        user=p1,
        at=datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
    )
    submit_daily_answer(assignment=day_three, user=p1, text_answer="day three p1")
    submit_daily_answer(assignment=day_three, user=p2, text_answer="day three p2")
    streak = CoupleStreak.objects.get(couple=couple)
    assert streak.current_count == 1
    assert streak.longest_count == 1

    day_four = get_or_create_daily_assignment(
        couple=couple,
        user=p1,
        at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    )
    submit_daily_answer(assignment=day_four, user=p1, text_answer="day four p1")
    submit_daily_answer(assignment=day_four, user=p2, text_answer="day four p2")
    streak.refresh_from_db()
    assert streak.current_count == 2
    assert streak.longest_count == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_other_couple_cannot_view_or_answer_daily_assignment():
    partner_one, _ = create_active_couple()
    assignment_id = partner_one.get("/api/v1/daily/current/").json()["assignment"]["id"]

    other = authenticated_client("other-daily@example.com")
    other.post("/api/v1/couples/")

    view_response = other.get(f"/api/v1/daily/{assignment_id}/")
    answer_response = other.post(
        f"/api/v1/daily/{assignment_id}/answers/",
        {"text_answer": "not my assignment"},
        content_type="application/json",
    )

    assert view_response.status_code == 404
    assert answer_response.status_code == 404
