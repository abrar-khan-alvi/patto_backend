import pytest
from django.test import override_settings

from apps.accounts.models import User
from apps.ai.client import AIClientResponse
from apps.coach.models import CoachConversation, CoachMessage, CoachRun
from apps.coach.services import (
    add_coach_message,
    authorized_context_messages,
    create_coach_conversation,
    run_coach,
    share_individual_coach_message,
)
from tests.helpers import authenticated_client


class FakeCoachClient:
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
                "message": "That sounds tender. Try naming one small need and one appreciation.",
                "suggested_next_steps": ["Share one concrete request.", "Reflect back what you heard."],
                "safety_flags": [],
            },
            provider_response_id="coach-response-1",
            usage={"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
        )


def create_active_couple(prefix="coach"):
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
def test_individual_coach_conversation_is_private_to_owner():
    partner_one, partner_two = create_active_couple()

    response = partner_one.post(
        "/api/v1/coach/conversations/",
        {"scope": "individual", "title": "Private thoughts"},
        content_type="application/json",
    )
    conversation_id = response.json()["id"]
    partner_one.post(
        f"/api/v1/coach/conversations/{conversation_id}/messages/",
        {"body": "I am worried but not ready to share this."},
        content_type="application/json",
    )

    owner_view = partner_one.get(f"/api/v1/coach/conversations/{conversation_id}/")
    partner_view = partner_two.get(f"/api/v1/coach/conversations/{conversation_id}/")

    assert response.status_code == 201
    assert owner_view.status_code == 200
    assert partner_view.status_code == 403


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_couple_coach_context_excludes_unshared_individual_messages():
    create_active_couple("coach-context")
    p1 = User.objects.get(email="coach-context-p1@example.com")
    couple = p1.couple_memberships.select_related("couple").get().couple
    individual = create_coach_conversation(user=p1, scope=CoachConversation.Scope.INDIVIDUAL)
    private_message = add_coach_message(conversation=individual, user=p1, body="Private individual Coach content.")
    couple_conversation = create_coach_conversation(user=p1, scope=CoachConversation.Scope.COUPLE, title="Shared Coach")
    add_coach_message(conversation=couple_conversation, user=p1, body="Shared couple message.")

    context = authorized_context_messages(conversation=couple_conversation, user=p1)

    assert private_message not in context
    assert all(message.body != "Private individual Coach content." for message in context)
    assert couple_conversation.couple == couple


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_explicitly_shared_individual_message_enters_couple_context():
    create_active_couple("coach-share")
    p1 = User.objects.get(email="coach-share-p1@example.com")
    individual = create_coach_conversation(user=p1, scope=CoachConversation.Scope.INDIVIDUAL)
    private_message = add_coach_message(conversation=individual, user=p1, body="I explicitly choose to share this.")
    share_individual_coach_message(message=private_message, user=p1)
    couple_conversation = create_coach_conversation(user=p1, scope=CoachConversation.Scope.COUPLE, title="Shared Coach")

    context = authorized_context_messages(conversation=couple_conversation, user=p1)

    assert private_message in context
    assert any(message.body == "I explicitly choose to share this." for message in context)


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_individual_coach_run_uses_authorized_context_and_persists_ai_message():
    create_active_couple("coach-run")
    p1 = User.objects.get(email="coach-run-p1@example.com")
    individual = create_coach_conversation(user=p1, scope=CoachConversation.Scope.INDIVIDUAL)
    private_message = add_coach_message(conversation=individual, user=p1, body="Help me think through a hard feeling.")
    client = FakeCoachClient()

    run = run_coach(conversation=individual, user=p1, client=client)

    prompt_text = client.calls[0]["input_messages"][-1]["content"]
    assert run.status == CoachRun.Status.SUCCEEDED
    assert run.provider_response_id == "coach-response-1"
    assert run.response_message.body.startswith("That sounds tender")
    assert str(private_message.id) in run.context_message_ids
    assert "Help me think through a hard feeling." in prompt_text
    assert CoachMessage.objects.filter(conversation=individual, sender_type=CoachMessage.SenderType.AI).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_couple_chat_has_no_ai_run_or_ai_message():
    partner_one, partner_two = create_active_couple("couple-chat")
    response = partner_one.post(
        "/api/v1/coach/conversations/",
        {"scope": "couple", "title": "Partner chat"},
        content_type="application/json",
    )
    conversation_id = response.json()["id"]
    message_response = partner_two.post(
        f"/api/v1/coach/conversations/{conversation_id}/messages/",
        {"body": "This is a partner-to-partner message."},
        content_type="application/json",
    )
    run_response = partner_one.post(f"/api/v1/coach/conversations/{conversation_id}/run/")

    assert response.status_code == 201
    assert message_response.status_code == 201
    assert run_response.status_code == 400
    assert CoachMessage.objects.filter(conversation_id=conversation_id, sender_type=CoachMessage.SenderType.AI).count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_coach_api_create_message_run_and_share():
    partner_one, _ = create_active_couple("coach-api")
    individual_response = partner_one.post(
        "/api/v1/coach/conversations/",
        {"scope": "individual", "title": "Solo"},
        content_type="application/json",
    )
    conversation_id = individual_response.json()["id"]
    message_response = partner_one.post(
        f"/api/v1/coach/conversations/{conversation_id}/messages/",
        {"body": "A private message I may share later."},
        content_type="application/json",
    )
    share_response = partner_one.post(f"/api/v1/coach/messages/{message_response.json()['id']}/share/")
    run_response = partner_one.post(f"/api/v1/coach/conversations/{conversation_id}/run/")

    assert individual_response.status_code == 201
    assert message_response.status_code == 201
    assert share_response.status_code == 200
    assert share_response.json()["explicitly_shared_with_partner"] is True
    assert run_response.status_code == 201
    assert run_response.json()["status"] == CoachRun.Status.FAILED
    assert run_response.json()["error_code"] == "configuration_error"
