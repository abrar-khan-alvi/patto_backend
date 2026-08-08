import pytest
from django.test import override_settings

from apps.accounts.models import User
from apps.ai.client import AIClientResponse
from apps.conflicts.models import ConflictBridge, ConflictMessage, ConflictResolution, ConflictThread
from apps.conflicts.services import create_conflict_thread, run_conflict_bridge, submit_conflict_perspective, resolve_conflict
from apps.pacts.models import Pact
from tests.helpers import authenticated_client


class FakeConflictBridgeClient:
    def __init__(self, content=None):
        self.calls = []
        self.content = content or {
            "neutral_summary": "Both partners want the evening routine to feel calmer and more predictable.",
            "partner_summaries": {
                "partner_a": "One partner feels overwhelmed by last-minute changes.",
                "partner_b": "The other partner wants flexibility without feeling criticized.",
            },
            "common_ground": ["Both want less tension.", "Both care about planning fairly."],
            "next_steps": ["Name one predictable anchor for evenings.", "Choose one flexible backup plan."],
            "safety_flags": [],
        }

    def create_structured_response(self, *, model, input_messages, json_schema, schema_name):
        self.calls.append({"model": model, "input_messages": input_messages, "json_schema": json_schema, "schema_name": schema_name})
        return AIClientResponse(content=self.content, provider_response_id="conflict-bridge-1", usage={"total_tokens": 111})


def create_active_couple(prefix="conflict"):
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


def submit_locked_pair(thread, p1, p2):
    submit_conflict_perspective(
        thread=thread,
        user=p1,
        situation="I feel rushed when plans change at dinner time.",
        feelings="Overwhelmed",
        needs="Predictability",
        requested_outcome="Earlier planning",
        lock=True,
    )
    submit_conflict_perspective(
        thread=thread,
        user=p2,
        situation="I feel boxed in when every evening has to be fixed.",
        feelings="Constrained",
        needs="Some flexibility",
        requested_outcome="Room for changes",
        lock=True,
    )


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_private_perspectives_cannot_be_retrieved_early_by_partner():
    partner_one, partner_two = create_active_couple()
    create_response = partner_one.post("/api/v1/conflicts/", {"title": "Dinner planning"}, content_type="application/json")
    thread_id = create_response.json()["id"]
    partner_one.post(
        f"/api/v1/conflicts/{thread_id}/perspective/",
        {"situation": "Private p1 perspective", "feelings": "Tender", "lock": True},
        content_type="application/json",
    )

    p1_detail = partner_one.get(f"/api/v1/conflicts/{thread_id}/").json()
    p2_detail = partner_two.get(f"/api/v1/conflicts/{thread_id}/").json()

    assert len(p1_detail["perspectives"]) == 1
    assert p1_detail["perspectives"][0]["situation"] == "Private p1 perspective"
    assert p2_detail["perspectives"] == []


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_conflict_bridge_after_both_locked_opens_shared_discussion():
    create_active_couple("conflict-bridge")
    p1 = User.objects.get(email="conflict-bridge-p1@example.com")
    p2 = User.objects.get(email="conflict-bridge-p2@example.com")
    thread = create_conflict_thread(user=p1, title="Evening planning")
    submit_locked_pair(thread, p1, p2)
    thread.refresh_from_db()

    bridge = run_conflict_bridge(thread=thread, user=p1, client=FakeConflictBridgeClient())
    thread.refresh_from_db()

    assert thread.status == ConflictThread.Status.DISCUSSION_OPEN
    assert bridge.status == ConflictBridge.Status.SUCCEEDED
    assert "calmer" in bridge.neutral_summary
    assert ConflictMessage.objects.filter(thread=thread, sender_type=ConflictMessage.SenderType.AI).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_conflict_bridge_policy_blocks_blame_assignment():
    create_active_couple("conflict-blame")
    p1 = User.objects.get(email="conflict-blame-p1@example.com")
    p2 = User.objects.get(email="conflict-blame-p2@example.com")
    thread = create_conflict_thread(user=p1, title="Blame test")
    submit_locked_pair(thread, p1, p2)

    bridge = run_conflict_bridge(
        thread=thread,
        user=p1,
        client=FakeConflictBridgeClient(
            content={
                "neutral_summary": "Partner B is at fault and should apologize.",
                "partner_summaries": {},
                "common_ground": ["They both noticed tension."],
                "next_steps": ["Partner B should admit blame."],
                "safety_flags": [],
            }
        ),
    )

    assert bridge.status == ConflictBridge.Status.POLICY_BLOCKED
    assert bridge.error_code == "bridge_blame_detected"
    assert ConflictMessage.objects.filter(thread=thread).count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_conflict_resolution_never_edits_pact_automatically():
    create_active_couple("conflict-resolve")
    p1 = User.objects.get(email="conflict-resolve-p1@example.com")
    p2 = User.objects.get(email="conflict-resolve-p2@example.com")
    thread = create_conflict_thread(user=p1, title="Resolution")
    submit_locked_pair(thread, p1, p2)
    run_conflict_bridge(thread=thread, user=p1, client=FakeConflictBridgeClient())

    resolution = resolve_conflict(
        thread=thread,
        user=p1,
        summary="We agreed to try a planning pause.",
        proposed_pact_changes=["Add a Sunday planning ritual."],
    )

    assert isinstance(resolution, ConflictResolution)
    assert Pact.objects.count() == 0
    assert resolution.proposed_pact_changes == ["Add a Sunday planning ritual."]
    thread.refresh_from_db()
    assert thread.status == ConflictThread.Status.RESOLVED


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_conflict_api_full_flow_and_mediation_request():
    partner_one, partner_two = create_active_couple("conflict-api")
    create_response = partner_one.post("/api/v1/conflicts/", {"title": "Chores"}, content_type="application/json")
    thread_id = create_response.json()["id"]
    p1_perspective = partner_one.post(
        f"/api/v1/conflicts/{thread_id}/perspective/",
        {"situation": "I need more help with chores.", "needs": "Support", "lock": True},
        content_type="application/json",
    )
    p2_perspective = partner_two.post(
        f"/api/v1/conflicts/{thread_id}/perspective/",
        {"situation": "I need clearer requests.", "needs": "Clarity", "lock": True},
        content_type="application/json",
    )
    bridge_response = partner_one.post(f"/api/v1/conflicts/{thread_id}/bridge/")
    message_response = partner_two.post(
        f"/api/v1/conflicts/{thread_id}/messages/",
        {"body": "I can try clearer timing."},
        content_type="application/json",
    )
    mediation_response = partner_one.post(
        f"/api/v1/conflicts/{thread_id}/mediations/",
        {"prompt": "Help us discuss chores gently."},
        content_type="application/json",
    )

    assert create_response.status_code == 201
    assert p1_perspective.status_code == 200
    assert p2_perspective.status_code == 200
    assert bridge_response.status_code == 201
    assert bridge_response.json()["status"] == ConflictBridge.Status.FAILED
    assert bridge_response.json()["error_code"] == "configuration_error"
    # Open discussion manually for API message/mediation checks after dev-safe provider failure.
    thread = ConflictThread.objects.get(id=thread_id)
    thread.status = ConflictThread.Status.DISCUSSION_OPEN
    thread.save(update_fields=["status", "updated_at"])
    message_response = partner_two.post(
        f"/api/v1/conflicts/{thread_id}/messages/",
        {"body": "I can try clearer timing."},
        content_type="application/json",
    )
    mediation_response = partner_one.post(
        f"/api/v1/conflicts/{thread_id}/mediations/",
        {"prompt": "Help us discuss chores gently."},
        content_type="application/json",
    )
    assert message_response.status_code == 201
    assert mediation_response.status_code == 201
