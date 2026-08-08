import secrets
import string
import hashlib
import json
from datetime import timedelta

from django.forms.models import model_to_dict
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import AuthSession, UserProfile
from apps.billing.models import Subscription, SubscriptionEvent
from apps.billing.services import sync_entitlement_from_subscription
from apps.common.services import record_audit_event
from apps.couples.models import Couple, CoupleMember
from apps.couples.services import user_active_membership
from apps.profile_features.models import (
    AccountDeletionRequest,
    DataExportRequest,
    Referral,
    ReferralCode,
    ReferralReward,
    SubscriptionManagementRequest,
    SupportTicket,
    SupportTicketMessage,
)


PRIVATE_CONTENT_REMOVED = "[deleted by account owner]"


def generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "PATTO-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not ReferralCode.objects.filter(code=code).exists():
            return code


def get_or_create_referral_code(*, user) -> ReferralCode:
    code, _ = ReferralCode.objects.get_or_create(user=user, defaults={"code": generate_referral_code()})
    return code


@transaction.atomic
def apply_referral_code(*, user, code: str, request_id: str = "") -> Referral:
    referral_code = ReferralCode.objects.filter(code=code.strip().upper(), is_active=True).select_related("user").first()
    if referral_code is None:
        raise ValidationError({"code": "Referral code is invalid."})
    if referral_code.user_id == user.id:
        raise ValidationError({"code": "You cannot use your own referral code."})
    referral, created = Referral.objects.get_or_create(
        referred_user=user,
        defaults={
            "code": referral_code,
            "referrer": referral_code.user,
        },
    )
    if not created and referral.code_id != referral_code.id:
        raise ValidationError({"code": "A referral code has already been applied."})
    record_audit_event(action="referral.applied", actor=user, target=referral, request_id=request_id)
    return referral


@transaction.atomic
def maybe_grant_referral_reward_from_subscription_event(*, subscription: Subscription, event: SubscriptionEvent) -> ReferralReward | None:
    if subscription.status != Subscription.Status.ACTIVE or event.status != SubscriptionEvent.Status.PROCESSED:
        return None
    referral = Referral.objects.filter(referred_user=subscription.owner).select_related("referrer").first()
    if referral is None:
        return None
    referral.status = Referral.Status.REWARDED
    referral.verified_subscription = subscription
    referral.verified_event = event
    referral.verified_at = referral.verified_at or timezone.now()
    referral.save(update_fields=["status", "verified_subscription", "verified_event", "verified_at", "updated_at"])
    reward, _ = ReferralReward.objects.get_or_create(
        referral=referral,
        defaults={
            "referrer": referral.referrer,
            "source_event": event,
            "granted_at": timezone.now(),
            "metadata": {
                "subscription_id": str(subscription.id),
                "platform": subscription.platform,
                "origin": "verified_iap_event",
            },
        },
    )
    return reward


@transaction.atomic
def create_support_ticket(*, user, category: str, subject: str, body: str, request_id: str = "") -> SupportTicket:
    ticket = SupportTicket.objects.create(user=user, category=category, subject=subject.strip()[:180])
    SupportTicketMessage.objects.create(ticket=ticket, user=user, sender_type=SupportTicketMessage.SenderType.USER, body=body.strip())
    record_audit_event(action="support_ticket.created", actor=user, target=ticket, request_id=request_id)
    return ticket


@transaction.atomic
def add_support_ticket_message(*, ticket: SupportTicket, user, body: str, request_id: str = "") -> SupportTicketMessage:
    if ticket.user_id != user.id:
        raise PermissionDenied("You cannot access this support ticket.")
    message = SupportTicketMessage.objects.create(ticket=ticket, user=user, sender_type=SupportTicketMessage.SenderType.USER, body=body.strip())
    ticket.status = SupportTicket.Status.OPEN
    ticket.save(update_fields=["status", "updated_at"])
    record_audit_event(action="support_ticket.message_created", actor=user, target=ticket, request_id=request_id)
    return message


def current_subscription_management_payload(*, user) -> dict:
    membership = user_active_membership(user)
    subscriptions = []
    if membership is not None:
        subscriptions = list(membership.couple.subscriptions.order_by("-updated_at"))
    latest = subscriptions[0] if subscriptions else None
    return {
        "current_subscription": latest,
        "platform_management": {
            "apple": "Manage Apple subscriptions in the App Store subscription settings.",
            "google": "Manage Google Play subscriptions in Play Store payments and subscriptions.",
        },
    }


def create_subscription_management_request(*, user, request_type: str, platform: str = "", notes: str = "", request_id: str = "") -> SubscriptionManagementRequest:
    membership = user_active_membership(user)
    request_obj = SubscriptionManagementRequest.objects.create(
        user=user,
        couple=membership.couple if membership else None,
        request_type=request_type,
        platform=platform,
        notes=notes.strip(),
    )
    record_audit_event(action="subscription_management.requested", actor=user, target=request_obj, request_id=request_id)
    return request_obj


def create_data_export_request(*, user, request_id: str = "") -> DataExportRequest:
    existing = DataExportRequest.objects.filter(user=user, status__in=[DataExportRequest.Status.REQUESTED, DataExportRequest.Status.PROCESSING]).first()
    if existing is not None:
        return existing
    export_request = DataExportRequest.objects.create(user=user)
    record_audit_event(action="data_export.requested", actor=user, target=export_request, request_id=request_id)
    return export_request


def create_account_deletion_request(*, user, reason: str = "", request_id: str = "") -> AccountDeletionRequest:
    existing = AccountDeletionRequest.objects.filter(user=user, status__in=[AccountDeletionRequest.Status.REQUESTED, AccountDeletionRequest.Status.PROCESSING]).first()
    if existing is not None:
        return existing
    deletion_request = AccountDeletionRequest.objects.create(
        user=user,
        reason=reason.strip(),
        scheduled_for=timezone.now() + timedelta(days=7),
    )
    record_audit_event(action="account_deletion.requested", actor=user, target=deletion_request, request_id=request_id)
    return deletion_request


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_for_export(value):
    return json.loads(json.dumps(value, default=_json_default, sort_keys=True))


def _serialize_instance(instance, *, fields: list[str]) -> dict:
    return _normalize_for_export({field: getattr(instance, field) for field in fields})


def _membership_couple_ids(user) -> list:
    return list(CoupleMember.objects.filter(user=user).values_list("couple_id", flat=True).distinct())


def build_user_export_payload(*, user) -> dict:
    couple_ids = _membership_couple_ids(user)
    profile = UserProfile.objects.filter(user=user).first()
    memberships = CoupleMember.objects.filter(couple_id__in=couple_ids).select_related("user", "couple").order_by("couple_id", "role")

    from apps.coach.models import CoachConversation, CoachMessage
    from apps.conflicts.models import ConflictBridge, ConflictMessage, ConflictPerspective, ConflictResolution, ConflictThread
    from apps.daily.models import DailyAnswer
    from apps.moments.models import Moment, MomentMedia
    from apps.responses.models import TopicMemberCompletion, TopicResponse
    from apps.topics.models import CoupleTopic

    owned_conversations = CoachConversation.objects.filter(Q(owner=user) | Q(participants__user=user)).distinct().order_by("created_at")
    conversation_ids = list(owned_conversations.values_list("id", flat=True))
    visible_coach_messages = CoachMessage.objects.filter(
        Q(conversation_id__in=conversation_ids, conversation__scope=CoachConversation.Scope.COUPLE)
        | Q(conversation__owner=user)
        | Q(author=user)
        | Q(couple_id__in=couple_ids, explicitly_shared_with_partner=True)
    ).select_related("conversation", "author").distinct().order_by("created_at")

    conflict_threads = ConflictThread.objects.filter(couple_id__in=couple_ids).order_by("created_at")
    conflict_thread_ids = list(conflict_threads.values_list("id", flat=True))

    export = {
        "generated_at": timezone.now().isoformat(),
        "user": _serialize_instance(user, fields=["id", "email", "preferred_language", "timezone", "email_verified_at", "created_at", "updated_at"]),
        "profile": _serialize_instance(profile, fields=["id", "display_name", "pronouns", "preferred_language", "timezone", "onboarding_completed_at", "created_at", "updated_at"]) if profile else None,
        "couples": [
            {
                "id": str(couple.id),
                "status": couple.status,
                "created_at": couple.created_at.isoformat(),
                "members": [
                    {
                        "user_id": str(member.user_id),
                        "email": member.user.email,
                        "role": member.role,
                        "status": member.status,
                        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                        "left_at": member.left_at.isoformat() if member.left_at else None,
                    }
                    for member in memberships
                    if member.couple_id == couple.id
                ],
            }
            for couple in Couple.objects.filter(id__in=couple_ids).order_by("created_at")
        ],
        "support_tickets": [
            {
                **_serialize_instance(ticket, fields=["id", "category", "subject", "status", "created_at", "updated_at"]),
                "messages": [
                    _serialize_instance(message, fields=["id", "sender_type", "body", "created_at"])
                    for message in ticket.messages.order_by("created_at")
                ],
            }
            for ticket in SupportTicket.objects.filter(user=user).prefetch_related("messages").order_by("created_at")
        ],
        "subscription_management_requests": [
            _serialize_instance(request, fields=["id", "request_type", "platform", "notes", "created_at"])
            for request in SubscriptionManagementRequest.objects.filter(user=user).order_by("created_at")
        ],
        "billing_subscriptions_owned": [
            _serialize_instance(subscription, fields=["id", "couple_id", "platform", "product_id", "status", "starts_at", "expires_at", "revoked_at", "created_at", "updated_at"])
            for subscription in Subscription.objects.filter(owner=user).order_by("created_at")
        ],
        "custom_topics_created": [
            _serialize_instance(topic, fields=["id", "couple_id", "stable_key", "title", "description", "version", "is_active", "is_locked", "created_at", "updated_at"])
            for topic in CoupleTopic.objects.filter(created_by=user).order_by("created_at")
        ],
        "topic_responses": [
            _serialize_instance(response, fields=["id", "session_id", "couple_id", "user_id", "question_stable_key", "selected_option_key", "text_answer", "answered_at", "created_at", "updated_at"])
            for response in TopicResponse.objects.filter(user=user).order_by("created_at")
        ],
        "topic_completions": [
            _serialize_instance(completion, fields=["id", "session_id", "couple_id", "user_id", "completed_at", "created_at"])
            for completion in TopicMemberCompletion.objects.filter(user=user).order_by("created_at")
        ],
        "daily_answers": [
            _serialize_instance(answer, fields=["id", "assignment_id", "couple_id", "user_id", "text_answer", "answered_at", "created_at", "updated_at"])
            for answer in DailyAnswer.objects.filter(user=user).order_by("created_at")
        ],
        "coach_conversations": [
            _serialize_instance(conversation, fields=["id", "scope", "couple_id", "owner_id", "title", "status", "metadata", "archived_at", "created_at", "updated_at"])
            for conversation in owned_conversations
        ],
        "coach_messages": [
            _serialize_instance(message, fields=["id", "conversation_id", "couple_id", "author_id", "sender_type", "body", "explicitly_shared_with_partner", "shared_at", "created_at"])
            for message in visible_coach_messages
        ],
        "conflict_threads": [
            _serialize_instance(thread, fields=["id", "couple_id", "title", "status", "created_by_id", "resolved_at", "created_at", "updated_at"])
            for thread in conflict_threads
        ],
        "conflict_perspectives_owned": [
            _serialize_instance(perspective, fields=["id", "thread_id", "couple_id", "user_id", "situation", "feelings", "needs", "requested_outcome", "locked_at", "created_at", "updated_at"])
            for perspective in ConflictPerspective.objects.filter(user=user).order_by("created_at")
        ],
        "conflict_bridges_shared": [
            _serialize_instance(bridge, fields=["id", "thread_id", "couple_id", "status", "model", "neutral_summary", "common_ground", "partner_summaries", "next_steps", "safety_flags", "created_at", "updated_at"])
            for bridge in ConflictBridge.objects.filter(thread_id__in=conflict_thread_ids).order_by("created_at")
        ],
        "conflict_messages_shared": [
            _serialize_instance(message, fields=["id", "thread_id", "couple_id", "author_id", "sender_type", "body", "render_as", "metadata", "created_at"])
            for message in ConflictMessage.objects.filter(thread_id__in=conflict_thread_ids).order_by("created_at")
        ],
        "conflict_resolutions_shared": [
            _serialize_instance(resolution, fields=["id", "thread_id", "couple_id", "resolved_by_id", "summary", "proposed_pact_changes", "created_at"])
            for resolution in ConflictResolution.objects.filter(thread_id__in=conflict_thread_ids).order_by("created_at")
        ],
        "moments_shared": [
            _serialize_instance(moment, fields=["id", "couple_id", "created_by_id", "title", "body", "occurred_on", "status", "archived_at", "created_at", "updated_at"])
            for moment in Moment.objects.filter(couple_id__in=couple_ids).order_by("created_at")
        ],
        "moment_media_shared_metadata": [
            _serialize_instance(media, fields=["id", "moment_id", "couple_id", "uploaded_by_id", "filename", "content_type", "byte_size", "width", "height", "checksum_sha256", "metadata_removed", "created_at"])
            for media in MomentMedia.objects.filter(couple_id__in=couple_ids).order_by("created_at")
        ],
    }
    return export


@transaction.atomic
def process_data_export_request(*, export_request: DataExportRequest, request_id: str = "") -> DataExportRequest:
    export_request = DataExportRequest.objects.select_for_update().select_related("user").get(id=export_request.id)
    if export_request.status == DataExportRequest.Status.READY:
        return export_request
    export_request.status = DataExportRequest.Status.PROCESSING
    export_request.failure_reason = ""
    export_request.save(update_fields=["status", "failure_reason"])
    try:
        payload = build_user_export_payload(user=export_request.user)
        encoded = json.dumps(payload, default=_json_default, sort_keys=True, separators=(",", ":")).encode("utf-8")
        export_request.export_data = payload
        export_request.byte_size = len(encoded)
        export_request.checksum_sha256 = hashlib.sha256(encoded).hexdigest()
        export_request.status = DataExportRequest.Status.READY
        export_request.completed_at = timezone.now()
        export_request.failure_reason = ""
        export_request.save(update_fields=["export_data", "byte_size", "checksum_sha256", "status", "completed_at", "failure_reason"])
        record_audit_event(action="data_export.ready", actor=export_request.user, target=export_request, request_id=request_id)
    except Exception as exc:
        export_request.status = DataExportRequest.Status.FAILED
        export_request.failure_reason = str(exc)
        export_request.save(update_fields=["status", "failure_reason"])
        raise
    return export_request


def revoke_user_sessions_for_deletion(*, user) -> int:
    now = timezone.now()
    return AuthSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=now)


def update_billing_for_deletion(*, user) -> int:
    updated = 0
    now = timezone.now()
    subscriptions = Subscription.objects.filter(owner=user, status=Subscription.Status.ACTIVE).select_related("couple")
    for subscription in subscriptions:
        subscription.status = Subscription.Status.CANCELED
        subscription.revoked_at = subscription.revoked_at or now
        subscription.raw_latest_event = {
            **subscription.raw_latest_event,
            "account_deletion_requested": True,
            "account_deletion_updated_at": now.isoformat(),
        }
        subscription.save(update_fields=["status", "revoked_at", "raw_latest_event", "updated_at"])
        sync_entitlement_from_subscription(subscription)
        updated += 1
    return updated


def notify_partner_account_deletion_requested(*, deletion_request: AccountDeletionRequest) -> int:
    from apps.notifications.models import NotificationPreference
    from apps.notifications.services import emit_notification

    user = deletion_request.user
    active_memberships = CoupleMember.objects.filter(user=user, status=CoupleMember.Status.ACTIVE).select_related("couple")
    sent = 0
    for membership in active_memberships:
        partners = membership.couple.members.filter(status=CoupleMember.Status.ACTIVE).exclude(user=user).select_related("user")
        for partner in partners:
            notification = emit_notification(
                user=partner.user,
                couple=None,
                category=NotificationPreference.Category.ACCOUNT_DELETION_REQUESTED,
                event_key=f"account_deletion_requested:{deletion_request.id}:{partner.user_id}",
                title="Your partner disconnected",
                body="Your partner deleted their account or disconnected. Your previous shared couple data has been removed, and you can connect with a new partner.",
                data={"deletion_request_id": str(deletion_request.id), "couple_id": str(membership.couple_id)},
            )
            if notification is not None:
                sent += 1
    return sent


def delete_couples_for_account_deletion(*, user) -> str:
    action = AccountDeletionRequest.CoupleAction.NONE
    couple_ids = list(CoupleMember.objects.filter(user=user, status=CoupleMember.Status.ACTIVE).values_list("couple_id", flat=True))
    for couple in Couple.objects.filter(id__in=couple_ids):
        couple.delete()
        action = AccountDeletionRequest.CoupleAction.DELETED
    return action


def anonymize_user_private_content(*, user) -> None:
    from apps.coach.models import CoachMessage
    from apps.conflicts.models import ConflictMessage, ConflictPerspective
    from apps.daily.models import DailyAnswer
    from apps.responses.models import TopicResponse

    TopicResponse.objects.filter(user=user).update(text_answer=PRIVATE_CONTENT_REMOVED)
    DailyAnswer.objects.filter(user=user).update(text_answer=PRIVATE_CONTENT_REMOVED)
    CoachMessage.objects.filter(author=user).update(body=PRIVATE_CONTENT_REMOVED, metadata={})
    ConflictMessage.objects.filter(author=user).update(body=PRIVATE_CONTENT_REMOVED, metadata={})
    ConflictPerspective.objects.filter(user=user).update(
        situation=PRIVATE_CONTENT_REMOVED,
        feelings="",
        needs="",
        requested_outcome="",
    )
    SupportTicketMessage.objects.filter(user=user).update(body=PRIVATE_CONTENT_REMOVED)
    SupportTicket.objects.filter(user=user).update(subject=PRIVATE_CONTENT_REMOVED)
    DataExportRequest.objects.filter(user=user).update(export_data={}, byte_size=0, checksum_sha256="")

    UserProfile.objects.filter(user=user).update(display_name="", pronouns="", avatar="")
    user.email = f"deleted-{user.id}@deleted.patto.local"
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.email_verified_at = None
    user.last_login_at = None
    user.save(update_fields=["email", "first_name", "last_name", "is_active", "email_verified_at", "last_login_at", "updated_at"])


@transaction.atomic
def process_account_deletion_request(*, deletion_request: AccountDeletionRequest, request_id: str = "") -> AccountDeletionRequest:
    deletion_request = AccountDeletionRequest.objects.select_for_update().select_related("user").get(id=deletion_request.id)
    if deletion_request.status == AccountDeletionRequest.Status.COMPLETED:
        return deletion_request
    if deletion_request.status == AccountDeletionRequest.Status.CANCELED:
        raise ValidationError({"deletion_request": "Canceled deletion requests cannot be processed."})

    deletion_request.status = AccountDeletionRequest.Status.PROCESSING
    deletion_request.processed_at = deletion_request.processed_at or timezone.now()
    deletion_request.failure_reason = ""
    deletion_request.save(update_fields=["status", "processed_at", "failure_reason"])

    try:
        revoke_user_sessions_for_deletion(user=deletion_request.user)
        deletion_request.sessions_revoked_at = deletion_request.sessions_revoked_at or timezone.now()
        deletion_request.save(update_fields=["sessions_revoked_at"])

        update_billing_for_deletion(user=deletion_request.user)
        deletion_request.billing_updated_at = deletion_request.billing_updated_at or timezone.now()
        deletion_request.save(update_fields=["billing_updated_at"])

        notify_partner_account_deletion_requested(deletion_request=deletion_request)
        deletion_request.partner_notified_at = deletion_request.partner_notified_at or timezone.now()
        deletion_request.save(update_fields=["partner_notified_at"])

        deletion_request.couple_action = delete_couples_for_account_deletion(user=deletion_request.user)
        deletion_request.save(update_fields=["couple_action"])

        anonymize_user_private_content(user=deletion_request.user)
        deletion_request.status = AccountDeletionRequest.Status.COMPLETED
        deletion_request.completed_at = timezone.now()
        deletion_request.failure_reason = ""
        deletion_request.save(update_fields=["status", "completed_at", "failure_reason"])
        record_audit_event(action="account_deletion.completed", actor=None, target=deletion_request, request_id=request_id)
    except Exception as exc:
        deletion_request.failure_reason = str(exc)
        deletion_request.save(update_fields=["failure_reason"])
        raise
    return deletion_request
