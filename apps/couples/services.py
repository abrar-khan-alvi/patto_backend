import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.accounts.services import normalize_email
from apps.accounts.tokens import hash_secret
from apps.common.services import record_audit_event
from apps.couples.models import Couple, CoupleMember, Entitlement, PartnerInvitation


@dataclass(frozen=True)
class InvitationResult:
    invitation: PartnerInvitation
    token: str
    invite_url: str


def user_active_membership(user: User) -> CoupleMember | None:
    return (
        CoupleMember.objects.select_related("couple")
        .filter(user=user, status=CoupleMember.Status.ACTIVE)
        .first()
    )


def active_member_count(couple: Couple) -> int:
    return CoupleMember.objects.filter(couple=couple, status=CoupleMember.Status.ACTIVE).count()


def has_active_entitlement(couple: Couple) -> bool:
    now = timezone.now()
    return Entitlement.objects.filter(
        couple=couple,
        starts_at__lte=now,
        revoked_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists()


@transaction.atomic
def create_couple(*, creator: User, request_id: str = "") -> Couple:
    if user_active_membership(creator) is not None:
        raise ValidationError({"couple": "User already belongs to an active couple."})

    now = timezone.now()
    couple = Couple.objects.create(created_by=creator)
    CoupleMember.objects.create(
        couple=couple,
        user=creator,
        role=CoupleMember.Role.PARTNER_1,
        status=CoupleMember.Status.ACTIVE,
        joined_at=now,
    )
    record_audit_event(action="couple.created", actor=creator, target=couple, request_id=request_id)
    return couple


@transaction.atomic
def create_partner_invitation(
    *,
    couple: Couple,
    invited_by: User,
    email: str,
    request_id: str = "",
) -> InvitationResult:
    membership = CoupleMember.objects.filter(
        couple=couple,
        user=invited_by,
        status=CoupleMember.Status.ACTIVE,
    ).first()
    if membership is None:
        raise PermissionDenied("Only an active couple member can invite a partner.")
    if membership.role != CoupleMember.Role.PARTNER_1:
        raise PermissionDenied("Only Partner 1 can invite a partner during MVP.")
    if couple.status not in {Couple.Status.PENDING, Couple.Status.ACTIVE}:
        raise ValidationError({"couple": "Cannot invite a partner to this couple."})
    if active_member_count(couple) >= 2:
        raise ValidationError({"couple": "This couple already has two active partners."})

    token = secrets.token_urlsafe(48)
    normalized_email = normalize_email(email)
    invitation = PartnerInvitation.objects.create(
        couple=couple,
        invited_by=invited_by,
        email=normalized_email,
        token_hash=hash_secret(token),
        expires_at=timezone.now() + timedelta(days=settings.PARTNER_INVITATION_TTL_DAYS),
    )
    invite_url = settings.PARTNER_INVITATION_URL_TEMPLATE.format(token=token)
    send_mail(
        subject="You're invited to join Patto",
        message=f"You have been invited to join Patto. Open this link to accept: {invite_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalized_email],
        fail_silently=False,
    )
    record_audit_event(
        action="partner_invitation.created",
        actor=invited_by,
        target=invitation,
        request_id=request_id,
        metadata={"couple_id": str(couple.id)},
    )
    from apps.notifications.services import notify_partner_invitation_created

    notify_partner_invitation_created(invitation=invitation)
    return InvitationResult(invitation=invitation, token=token, invite_url=invite_url)


@transaction.atomic
def accept_partner_invitation(*, token: str, accepted_by: User, request_id: str = "") -> Couple:
    now = timezone.now()
    invitation = (
        PartnerInvitation.objects.select_for_update()
        .select_related("couple")
        .filter(token_hash=hash_secret(token))
        .first()
    )
    if invitation is None:
        raise ValidationError({"token": "Invitation is invalid or expired."})
    if invitation.revoked_at is not None or invitation.accepted_at is not None:
        raise ValidationError({"token": "Invitation is invalid or expired."})
    if invitation.expires_at <= now:
        raise ValidationError({"token": "Invitation is invalid or expired."})
    if user_active_membership(accepted_by) is not None:
        raise ValidationError({"couple": "User already belongs to an active couple."})

    couple = Couple.objects.select_for_update().get(id=invitation.couple_id)
    if active_member_count(couple) >= 2:
        raise ValidationError({"couple": "This couple already has two active partners."})

    CoupleMember.objects.create(
        couple=couple,
        user=accepted_by,
        role=CoupleMember.Role.PARTNER_2,
        status=CoupleMember.Status.ACTIVE,
        joined_at=now,
    )
    invitation.accepted_by = accepted_by
    invitation.accepted_at = now
    invitation.save(update_fields=["accepted_by", "accepted_at", "updated_at"])

    if couple.status == Couple.Status.PENDING:
        couple.status = Couple.Status.ACTIVE
        couple.activated_at = now
        couple.save(update_fields=["status", "activated_at", "updated_at"])

    record_audit_event(
        action="partner_invitation.accepted",
        actor=accepted_by,
        target=invitation,
        request_id=request_id,
        metadata={"couple_id": str(couple.id)},
    )
    from apps.notifications.services import notify_partner_joined

    notify_partner_joined(invitation=invitation)
    return couple


@transaction.atomic
def revoke_partner_invitation(*, invitation: PartnerInvitation, revoked_by: User, request_id: str = "") -> None:
    active_member = CoupleMember.objects.filter(
        couple=invitation.couple,
        user=revoked_by,
        status=CoupleMember.Status.ACTIVE,
    ).first()
    if active_member is None or active_member.role != CoupleMember.Role.PARTNER_1:
        raise PermissionDenied("Only Partner 1 can revoke this invitation.")
    if invitation.accepted_at is not None:
        raise ValidationError({"invitation": "Accepted invitations cannot be revoked."})
    if invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at", "updated_at"])
        record_audit_event(
            action="partner_invitation.revoked",
            actor=revoked_by,
            target=invitation,
            request_id=request_id,
            metadata={"couple_id": str(invitation.couple_id)},
        )
