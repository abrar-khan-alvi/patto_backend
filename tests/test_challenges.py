import pytest
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.challenges.models import Challenge, ChallengeAssignment, ChallengeMemberCompletion
from apps.challenges.services import assign_ai_suggested_challenge, assign_curated_challenge, complete_challenge_assignment
from tests.helpers import authenticated_client


def create_active_couple(prefix="challenge"):
    partner_one = authenticated_client(f"{prefix}-p1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": f"{prefix}-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client(f"{prefix}-p2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_challenge_completion_is_independent_for_each_partner():
    create_active_couple()
    p1 = User.objects.get(email="challenge-p1@example.com")
    p2 = User.objects.get(email="challenge-p2@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple
    challenge = Challenge.objects.filter(is_active=True).first()
    assignment = assign_curated_challenge(couple=couple, user=p1, challenge=challenge)

    first_completion = complete_challenge_assignment(assignment=assignment, user=p1, note="Done from my side.")
    assignment.refresh_from_db()
    assert first_completion.user == p1
    assert assignment.status == ChallengeAssignment.Status.ACTIVE
    assert ChallengeMemberCompletion.objects.filter(assignment=assignment).count() == 1

    complete_challenge_assignment(assignment=assignment, user=p2, note="Done too.")
    assignment.refresh_from_db()
    assert assignment.status == ChallengeAssignment.Status.COMPLETED
    assert ChallengeMemberCompletion.objects.filter(assignment=assignment).count() == 2


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_unsafe_or_coercive_ai_suggested_challenge_is_rejected():
    create_active_couple("unsafe-challenge")
    p1 = User.objects.get(email="unsafe-challenge-p1@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple

    with pytest.raises(ValidationError) as exc:
        assign_ai_suggested_challenge(
            couple=couple,
            user=p1,
            suggestion={
                "title": "Control their choices",
                "description": "Track their phone and punish them with silent treatment if they do not obey.",
                "instructions": "Make them prove they care.",
            },
        )

    assert "coercive" in str(exc.value).lower()
    assert ChallengeAssignment.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_generation_failure_uses_safe_fallback_challenge():
    create_active_couple("fallback-challenge")
    p1 = User.objects.get(email="fallback-challenge-p1@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple

    assignment = assign_ai_suggested_challenge(
        couple=couple,
        user=p1,
        suggestion=None,
        generation_failed=True,
    )

    assert assignment.source == ChallengeAssignment.AssignmentSource.FALLBACK
    assert assignment.challenge.source == Challenge.Source.FALLBACK
    assert assignment.fallback_reason == "generation_failed"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_safe_ai_suggested_challenge_can_be_assigned_after_policy_validation():
    create_active_couple("safe-ai-challenge")
    p1 = User.objects.get(email="safe-ai-challenge-p1@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple

    assignment = assign_ai_suggested_challenge(
        couple=couple,
        user=p1,
        suggestion={
            "title": "Kind weekly support plan",
            "description": "Ask each other what kind support would feel useful this week and choose one small action together.",
            "instructions": "Listen first, then each partner shares one gentle request.",
            "category": "communication",
            "duration_days": 2,
        },
    )

    assert assignment.source == ChallengeAssignment.AssignmentSource.AI_SUGGESTED
    assert assignment.challenge.source == Challenge.Source.AI_SUGGESTED
    assert assignment.challenge.is_active is False
    assert assignment.safety_flags == []


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_challenge_api_assignment_completion_and_cross_couple_isolation():
    partner_one, partner_two = create_active_couple("api-challenge")
    challenge = Challenge.objects.filter(is_active=True).first()

    catalog_response = partner_one.get("/api/v1/challenges/")
    create_response = partner_one.post(
        "/api/v1/challenge-assignments/",
        {"challenge_id": str(challenge.id)},
        content_type="application/json",
    )
    assignment_id = create_response.json()["id"]
    first_completion = partner_one.post(
        f"/api/v1/challenge-assignments/{assignment_id}/complete/",
        {"note": "I did my part."},
        content_type="application/json",
    )
    second_completion = partner_two.post(
        f"/api/v1/challenge-assignments/{assignment_id}/complete/",
        {"note": "Me too."},
        content_type="application/json",
    )
    outsider = authenticated_client("challenge-outsider@example.com")
    outsider.post("/api/v1/couples/")
    outsider_view = outsider.get(f"/api/v1/challenge-assignments/{assignment_id}/")

    assert catalog_response.status_code == 200
    assert len(catalog_response.json()["results"]) >= 1
    assert create_response.status_code == 201
    assert first_completion.status_code == 200
    assert first_completion.json()["status"] == ChallengeAssignment.Status.ACTIVE
    assert second_completion.status_code == 200
    assert second_completion.json()["status"] == ChallengeAssignment.Status.COMPLETED
    assert outsider_view.status_code == 404
