import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.coach.admin import CoachMessageAdmin
from apps.coach.models import CoachConversation, CoachMessage
from apps.common.admin import SENSITIVE_CONTENT_ACCESS_GROUP, has_sensitive_admin_access
from apps.common.models import AuditEvent
from apps.couples.models import Couple, CoupleMember
from apps.responses.admin import TopicResponseAdmin
from apps.responses.models import TopicResponse, TopicSession


def create_couple_with_user(email="admin-user@example.com"):
    user = User.objects.create_user(email=email)
    couple = Couple.objects.create(created_by=user, status=Couple.Status.ACTIVE, activated_at=timezone.now())
    CoupleMember.objects.create(couple=couple, user=user, role=CoupleMember.Role.PARTNER_1, status=CoupleMember.Status.ACTIVE, joined_at=timezone.now())
    return user, couple


def create_topic_response():
    user, couple = create_couple_with_user()
    session = TopicSession.objects.create(
        couple=couple,
        topic_kind=TopicSession.TopicKind.BUILT_IN,
        topic_stable_key="money",
        topic_version=1,
        expected_question_count=1,
    )
    return TopicResponse.objects.create(
        session=session,
        couple=couple,
        user=user,
        question_stable_key="money-plan",
        question_version=1,
        text_answer="This is private.",
        answered_at=timezone.now(),
    )


@pytest.mark.django_db
def test_sensitive_admin_fields_are_redacted_for_default_staff():
    staff = User.objects.create_user(email="staff@example.com", is_staff=True)
    request = RequestFactory().get("/admin/")
    request.user = staff
    response_admin = TopicResponseAdmin(TopicResponse, admin.site)

    fields = response_admin.get_fields(request)

    assert "text_answer" not in fields
    assert "redacted_text_answer" in fields
    assert has_sensitive_admin_access(request) is False


@pytest.mark.django_db
def test_sensitive_admin_fields_are_available_to_group_members():
    staff = User.objects.create_user(email="sensitive-staff@example.com", is_staff=True)
    group = Group.objects.create(name=SENSITIVE_CONTENT_ACCESS_GROUP)
    staff.groups.add(group)
    request = RequestFactory().get("/admin/")
    request.user = staff
    response_admin = TopicResponseAdmin(TopicResponse, admin.site)

    fields = response_admin.get_fields(request)

    assert "text_answer" in fields
    assert "redacted_text_answer" not in fields
    assert has_sensitive_admin_access(request) is True


@pytest.mark.django_db
def test_sensitive_admin_detail_view_is_audited_for_superuser(client):
    response = create_topic_response()
    superuser = User.objects.create_superuser(email="super@example.com", password="test-pass-123")
    client.force_login(superuser)

    url = reverse("admin:responses_topicresponse_change", args=[response.id])
    admin_response = client.get(url)

    assert admin_response.status_code == 200
    assert AuditEvent.objects.filter(
        action="admin.sensitive_content_viewed",
        actor=superuser,
        target_type="TopicResponse",
        target_id=str(response.id),
    ).exists()


@pytest.mark.django_db
def test_coach_message_admin_does_not_search_private_body():
    message_admin = CoachMessageAdmin(CoachMessage, admin.site)

    assert "body" not in message_admin.search_fields


@pytest.mark.django_db
def test_coach_message_inline_metadata_is_available_without_message_body():
    user, couple = create_couple_with_user("coach-admin@example.com")
    conversation = CoachConversation.objects.create(scope=CoachConversation.Scope.INDIVIDUAL, owner=user, couple=couple)
    message = CoachMessage.objects.create(conversation=conversation, couple=couple, author=user, sender_type=CoachMessage.SenderType.USER, body="Private coach message")
    request = RequestFactory().get("/admin/")
    request.user = User.objects.create_user(email="default-staff@example.com", is_staff=True)
    message_admin = CoachMessageAdmin(CoachMessage, admin.site)

    fields = message_admin.get_fields(request, obj=message)

    assert "body" not in fields
    assert "redacted_body" in fields
