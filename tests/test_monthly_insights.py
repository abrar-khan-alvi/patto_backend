from datetime import UTC, datetime

import pytest
from django.test import override_settings

from apps.accounts.models import User
from apps.ai.client import AIClientResponse
from apps.daily.services import get_or_create_daily_assignment, submit_daily_answer
from apps.insights.models import MonthlyInsight, MonthlyInsightInput
from apps.insights.services import get_or_create_monthly_insight_job, run_monthly_insight
from tests.helpers import authenticated_client


class FakeMonthlyInsightClient:
    def __init__(self):
        self.calls = []

    def create_structured_response(self, *, model, input_messages, json_schema, schema_name):
        self.calls.append(
            {
                "model": model,
                "input_messages": input_messages,
                "json_schema": json_schema,
                "schema_name": schema_name,
            }
        )
        return AIClientResponse(
            content={
                "month_summary": "You showed steady care through small check-ins this month.",
                "connection_patterns": ["You both name practical support clearly."],
                "growth_opportunities": ["Make repair gestures more explicit after stressful days."],
                "suggested_rituals": ["End Sundays with a ten-minute planning check-in."],
                "sections": [
                    {
                        "title": "Support rhythm",
                        "body": "Your answers suggest daily support lands best when it is concrete and calm.",
                        "highlights": ["Practical help", "Gentle appreciation"],
                    }
                ],
                "safety_flags": [],
            },
            provider_response_id="monthly-response-1",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )


def create_active_couple():
    partner_one = authenticated_client("insights-p1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "insights-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client("insights-p2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return partner_one, partner_two


def reveal_daily_for_date(*, couple, p1, p2, at, text_prefix):
    assignment = get_or_create_daily_assignment(couple=couple, user=p1, at=at)
    submit_daily_answer(assignment=assignment, user=p1, text_answer=f"{text_prefix} partner one")
    submit_daily_answer(assignment=assignment, user=p2, text_answer=f"{text_prefix} partner two")
    assignment.refresh_from_db()
    return assignment


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", MONTHLY_INSIGHT_MIN_REVEALED_DAYS=2)
def test_monthly_insight_succeeds_and_stores_ai_metadata():
    create_active_couple()
    p1 = User.objects.get(email="insights-p1@example.com")
    p2 = User.objects.get(email="insights-p2@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC), text_prefix="July 2")
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 7, 4, 12, 0, tzinfo=UTC), text_prefix="July 4")

    insight = get_or_create_monthly_insight_job(
        couple=couple,
        user=p1,
        year=2026,
        month=7,
        at=datetime(2026, 8, 1, 1, 0, tzinfo=UTC),
    )
    result = run_monthly_insight(insight_id=insight.id, client=FakeMonthlyInsightClient())

    assert result.status == MonthlyInsight.Status.SUCCEEDED
    assert result.prompt_version.key == "monthly_insight"
    assert result.provider_response_id == "monthly-response-1"
    assert result.sections["month_summary"].startswith("You showed steady care")
    assert result.usage["total_tokens"] == 150
    assert result.revealed_day_count == 2
    assert MonthlyInsightInput.objects.filter(insight=result).count() == 4


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", MONTHLY_INSIGHT_MIN_REVEALED_DAYS=2)
def test_monthly_insight_cannot_include_answers_outside_assigned_month():
    create_active_couple()
    p1 = User.objects.get(email="insights-p1@example.com")
    p2 = User.objects.get(email="insights-p2@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC), text_prefix="June outside")
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC), text_prefix="July inside")
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC), text_prefix="July end")
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC), text_prefix="August outside")
    client = FakeMonthlyInsightClient()

    insight = get_or_create_monthly_insight_job(
        couple=couple,
        user=p1,
        year=2026,
        month=7,
        at=datetime(2026, 8, 2, 1, 0, tzinfo=UTC),
    )
    result = run_monthly_insight(insight_id=insight.id, client=client)

    input_dates = set(MonthlyInsightInput.objects.filter(insight=result).values_list("local_date", flat=True))
    assert {item.isoformat() for item in input_dates} == {"2026-07-01", "2026-07-31"}
    prompt_payload = client.calls[0]["input_messages"][-1]["content"]
    assert "July inside" in prompt_payload
    assert "July end" in prompt_payload
    assert "June outside" not in prompt_payload
    assert "August outside" not in prompt_payload


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", MONTHLY_INSIGHT_MIN_REVEALED_DAYS=3)
def test_monthly_insight_is_ineligible_below_minimum_participation():
    create_active_couple()
    p1 = User.objects.get(email="insights-p1@example.com")
    p2 = User.objects.get(email="insights-p2@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple
    reveal_daily_for_date(couple=couple, p1=p1, p2=p2, at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC), text_prefix="Only one day")

    insight = get_or_create_monthly_insight_job(
        couple=couple,
        user=p1,
        year=2026,
        month=7,
        at=datetime(2026, 8, 1, 1, 0, tzinfo=UTC),
    )
    result = run_monthly_insight(insight_id=insight.id, client=FakeMonthlyInsightClient())

    assert result.status == MonthlyInsight.Status.INELIGIBLE
    assert result.error_code == "minimum_participation_not_met"
    assert result.revealed_day_count == 1
    assert MonthlyInsightInput.objects.filter(insight=result).count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_monthly_insight_job_requires_closed_month():
    create_active_couple()
    p1 = User.objects.get(email="insights-p1@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple

    with pytest.raises(Exception) as exc:
        get_or_create_monthly_insight_job(
            couple=couple,
            user=p1,
            year=2026,
            month=8,
            at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )

    assert "month closes" in str(exc.value)


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_monthly_insight_api_queues_closed_month_without_auto_dispatch():
    partner_one, _ = create_active_couple()

    response = partner_one.post(
        "/api/v1/monthly-insights/",
        {"year": 2026, "month": 7},
        content_type="application/json",
    )
    list_response = partner_one.get("/api/v1/monthly-insights/")

    assert response.status_code == 202
    assert response.json()["status"] == MonthlyInsight.Status.QUEUED
    assert list_response.status_code == 200
    assert len(list_response.json()["results"]) == 1
