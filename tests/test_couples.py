import re

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import hash_secret
from apps.couples.models import Couple, CoupleMember, PartnerInvitation
from tests.helpers import authenticated_client


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_user_can_create_pending_couple_as_partner_one():
    client = authenticated_client("partner1@example.com")

    response = client.post("/api/v1/couples/")

    assert response.status_code == 201
    couple = Couple.objects.get()
    assert couple.status == Couple.Status.PENDING
    member = CoupleMember.objects.get(couple=couple)
    assert member.role == CoupleMember.Role.PARTNER_1
    assert member.user.email == "partner1@example.com"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_active_user_cannot_create_second_couple():
    client = authenticated_client("partner1@example.com")
    assert client.post("/api/v1/couples/").status_code == 201

    response = client.post("/api/v1/couples/")

    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_one_can_invite_and_token_is_hashed():
    client = authenticated_client("partner1@example.com")
    couple_id = client.post("/api/v1/couples/").json()["id"]

    response = client.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "Partner2@Example.com"},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    invitation = PartnerInvitation.objects.get()
    assert invitation.email == "partner2@example.com"
    assert invitation.token_hash == hash_secret(body["token"])
    assert body["token"] not in invitation.token_hash
    assert len(mail.outbox) >= 2
    assert body["invite_url"] in mail.outbox[-1].body


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_partner_accepts_invitation_once_and_couple_becomes_active():
    partner_one = authenticated_client("partner1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    invite_response = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner2@example.com"},
        content_type="application/json",
    )
    token = invite_response.json()["token"]
    partner_two = authenticated_client("partner2@example.com")

    response = partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )

    assert response.status_code == 200
    couple = Couple.objects.get(id=couple_id)
    assert couple.status == Couple.Status.ACTIVE
    assert CoupleMember.objects.filter(couple=couple, status=CoupleMember.Status.ACTIVE).count() == 2
    assert PartnerInvitation.objects.get().accepted_by.email == "partner2@example.com"

    second_response = partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    assert second_response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_third_partner_cannot_join_couple():
    partner_one = authenticated_client("partner1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    first_invite = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner2@example.com"},
        content_type="application/json",
    ).json()["token"]
    authenticated_client("partner2@example.com").post(
        "/api/v1/couples/invitations/accept/",
        {"token": first_invite},
        content_type="application/json",
    )

    response = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "third@example.com"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_revoked_and_expired_invitations_cannot_be_accepted():
    partner_one = authenticated_client("partner1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    invite_body = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner2@example.com"},
        content_type="application/json",
    ).json()
    invitation_id = invite_body["invitation"]["id"]
    revoke_response = partner_one.post(f"/api/v1/couples/invitations/{invitation_id}/revoke/")
    assert revoke_response.status_code == 204

    partner_two = authenticated_client("partner2@example.com")
    revoked_response = partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": invite_body["token"]},
        content_type="application/json",
    )
    assert revoked_response.status_code == 400

    expired_token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner2@example.com"},
        content_type="application/json",
    ).json()["token"]
    invitation = PartnerInvitation.objects.order_by("-created_at").first()
    invitation.expires_at = timezone.now()
    invitation.save(update_fields=["expires_at"])

    expired_response = partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": expired_token},
        content_type="application/json",
    )
    assert expired_response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_unrelated_user_cannot_invite_to_someone_elses_couple():
    owner = authenticated_client("owner@example.com")
    couple_id = owner.post("/api/v1/couples/").json()["id"]
    outsider = authenticated_client("outsider@example.com")

    response = outsider.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": "partner@example.com"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert PartnerInvitation.objects.count() == 0
