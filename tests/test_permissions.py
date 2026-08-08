from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.couples.models import Couple, CoupleMember, Entitlement
from apps.couples.permissions import (
    CanCreatePartnerInvitation,
    HasActiveEntitlement,
    IsActiveCoupleMember,
    IsPartnerOne,
)


def request_for(user):
    return SimpleNamespace(user=user)


@pytest.fixture
def couple_with_partners():
    partner_one = User.objects.create_user(email="partner1@example.com")
    partner_two = User.objects.create_user(email="partner2@example.com")
    outsider = User.objects.create_user(email="outsider@example.com")
    couple = Couple.objects.create(
        created_by=partner_one,
        status=Couple.Status.ACTIVE,
        activated_at=timezone.now(),
    )
    CoupleMember.objects.create(
        couple=couple,
        user=partner_one,
        role=CoupleMember.Role.PARTNER_1,
        status=CoupleMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    CoupleMember.objects.create(
        couple=couple,
        user=partner_two,
        role=CoupleMember.Role.PARTNER_2,
        status=CoupleMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    return couple, partner_one, partner_two, outsider


@pytest.mark.django_db
def test_is_active_couple_member_rejects_outsiders_and_archived_couples(couple_with_partners):
    couple, partner_one, _, outsider = couple_with_partners
    permission = IsActiveCoupleMember()

    assert permission.has_object_permission(request_for(partner_one), None, couple) is True
    assert permission.has_object_permission(request_for(outsider), None, couple) is False

    couple.status = Couple.Status.ARCHIVED
    couple.save(update_fields=["status", "updated_at"])
    assert permission.has_object_permission(request_for(partner_one), None, couple) is False


@pytest.mark.django_db
def test_partner_one_permission_rejects_partner_two(couple_with_partners):
    couple, partner_one, partner_two, _ = couple_with_partners
    permission = IsPartnerOne()

    assert permission.has_object_permission(request_for(partner_one), None, couple) is True
    assert permission.has_object_permission(request_for(partner_two), None, couple) is False


@pytest.mark.django_db
def test_invitation_permission_allows_pending_partner_one():
    partner_one = User.objects.create_user(email="partner1@example.com")
    couple = Couple.objects.create(created_by=partner_one, status=Couple.Status.PENDING)
    CoupleMember.objects.create(
        couple=couple,
        user=partner_one,
        role=CoupleMember.Role.PARTNER_1,
        status=CoupleMember.Status.ACTIVE,
        joined_at=timezone.now(),
    )

    assert CanCreatePartnerInvitation().has_object_permission(request_for(partner_one), None, couple) is True


@pytest.mark.django_db
def test_has_active_entitlement_checks_current_unrevoked_window(couple_with_partners):
    couple, partner_one, _, _ = couple_with_partners
    permission = HasActiveEntitlement()
    now = timezone.now()

    assert permission.has_object_permission(request_for(partner_one), None, couple) is False

    entitlement = Entitlement.objects.create(
        couple=couple,
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )
    assert permission.has_object_permission(request_for(partner_one), None, couple) is True

    entitlement.revoked_at = now
    entitlement.save(update_fields=["revoked_at", "updated_at"])
    assert permission.has_object_permission(request_for(partner_one), None, couple) is False
