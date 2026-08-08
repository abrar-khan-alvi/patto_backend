from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Device, Notification, NotificationDelivery, NotificationPreference


@transaction.atomic
def register_device(*, user, platform: str, token: str, name: str = "") -> Device:
    device, _ = Device.objects.update_or_create(
        token=token,
        defaults={
            "user": user,
            "platform": platform,
            "name": name.strip()[:120],
            "is_active": True,
            "revoked_at": None,
        },
    )
    return device


@transaction.atomic
def revoke_device(*, device: Device, user) -> Device:
    if device.user_id != user.id:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("You cannot revoke this device.")
    device.is_active = False
    device.revoked_at = timezone.now()
    device.save(update_fields=["is_active", "revoked_at", "updated_at"])
    return device


@transaction.atomic
def set_notification_preference(*, user, category: str, enabled: bool) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.update_or_create(
        user=user,
        category=category,
        defaults={"enabled": enabled},
    )
    return preference


def notification_enabled(*, user, category: str) -> bool:
    preference = NotificationPreference.objects.filter(user=user, category=category).first()
    return True if preference is None else preference.enabled


@transaction.atomic
def emit_notification(
    *,
    user,
    category: str,
    event_key: str,
    title: str,
    body: str,
    couple=None,
    data: dict | None = None,
) -> Notification | None:
    if not notification_enabled(user=user, category=category):
        notification, _ = Notification.objects.get_or_create(
            user=user,
            event_key=event_key,
            defaults={
                "couple": couple,
                "category": category,
                "title": title,
                "body": body,
                "data": data or {},
                "status": Notification.Status.SUPPRESSED,
                "suppressed_at": timezone.now(),
            },
        )
        NotificationDelivery.objects.get_or_create(
            notification=notification,
            device=None,
            defaults={"status": NotificationDelivery.Status.SUPPRESSED},
        )
        return None

    notification, created = Notification.objects.get_or_create(
        user=user,
        event_key=event_key,
        defaults={
            "couple": couple,
            "category": category,
            "title": title,
            "body": body,
            "data": data or {},
        },
    )
    if created:
        create_pending_deliveries(notification=notification)
    return notification


def create_pending_deliveries(*, notification: Notification) -> None:
    active_devices = Device.objects.filter(user=notification.user, is_active=True)
    for device in active_devices:
        NotificationDelivery.objects.get_or_create(
            notification=notification,
            device=device,
            defaults={"status": NotificationDelivery.Status.PENDING},
        )


@transaction.atomic
def mark_notification_read(*, notification: Notification, user) -> Notification:
    if notification.user_id != user.id:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("You cannot mark this notification.")
    notification.status = Notification.Status.READ
    notification.read_at = timezone.now()
    notification.save(update_fields=["status", "read_at", "updated_at"])
    return notification


def notify_partner_invitation_created(*, invitation) -> None:
    from apps.accounts.models import User

    invited_user = User.objects.filter(email=invitation.email).first()
    if invited_user is None:
        return
    emit_notification(
        user=invited_user,
        couple=invitation.couple,
        category=NotificationPreference.Category.PARTNER_INVITATION,
        event_key=f"partner_invitation:{invitation.id}",
        title="You have a Patto invitation",
        body="Your partner invited you to join a Patto couple.",
        data={"invitation_id": str(invitation.id), "couple_id": str(invitation.couple_id)},
    )


def notify_partner_joined(*, invitation) -> None:
    emit_notification(
        user=invitation.invited_by,
        couple=invitation.couple,
        category=NotificationPreference.Category.PARTNER_JOINED,
        event_key=f"partner_joined:{invitation.id}",
        title="Your partner joined",
        body="Your partner accepted the Patto invitation.",
        data={"invitation_id": str(invitation.id), "couple_id": str(invitation.couple_id)},
    )


def notify_topic_completed(*, completion) -> None:
    active_members = completion.couple.members.filter(status="active").select_related("user")
    for member in active_members:
        if member.user_id == completion.user_id:
            continue
        emit_notification(
            user=member.user,
            couple=completion.couple,
            category=NotificationPreference.Category.TOPIC_COMPLETED,
            event_key=f"topic_completed:{completion.id}:{member.user_id}",
            title="Your partner completed a topic",
            body="Your partner finished answering a topic. Open Patto to continue.",
            data={"session_id": str(completion.session_id), "completed_user_id": str(completion.user_id)},
        )


def notify_analysis_ready(*, analysis_job) -> None:
    active_members = analysis_job.couple.members.filter(status="active").select_related("user")
    for member in active_members:
        emit_notification(
            user=member.user,
            couple=analysis_job.couple,
            category=NotificationPreference.Category.ANALYSIS_READY,
            event_key=f"analysis_ready:{analysis_job.id}:{member.user_id}",
            title="Your analysis is ready",
            body="Your shared topic analysis is ready to review.",
            data={"analysis_job_id": str(analysis_job.id), "session_id": str(analysis_job.session_id)},
        )


def notify_pact_approval_required(*, version, actor=None) -> None:
    active_members = version.couple.members.filter(status="active").select_related("user")
    for member in active_members:
        if actor is not None and member.user_id == actor.id:
            continue
        emit_notification(
            user=member.user,
            couple=version.couple,
            category=NotificationPreference.Category.PACT_APPROVAL_REQUIRED,
            event_key=f"pact_approval_required:{version.id}:{member.user_id}",
            title="Pact approval needed",
            body="A pact version is ready for your review and approval.",
            data={"pact_id": str(version.pact_id), "version_id": str(version.id)},
        )


def notify_pact_activated(*, version) -> None:
    active_members = version.couple.members.filter(status="active").select_related("user")
    for member in active_members:
        emit_notification(
            user=member.user,
            couple=version.couple,
            category=NotificationPreference.Category.PACT_ACTIVATED,
            event_key=f"pact_activated:{version.id}:{member.user_id}",
            title="Your pact is live",
            body="Both partners approved the pact. Your live version is ready.",
            data={"pact_id": str(version.pact_id), "version_id": str(version.id)},
        )
