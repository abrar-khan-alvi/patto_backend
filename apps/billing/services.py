import hashlib
import json

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.billing.models import IAPPurchaseAccount, Subscription, SubscriptionEvent
from apps.billing.verifiers import VerifiedIAPPayload, verify_development_iap_payload
from apps.common.services import record_audit_event
from apps.couples.models import Couple, CoupleMember, Entitlement
from apps.couples.permissions import user_is_partner_one


ACTIVE_EVENT_TYPES = {"initial_buy", "renewal", "recovered", "product_change", "development_active"}
ENDED_EVENT_TYPES = {"expiration", "cancel", "refund", "revocation", "development_inactive"}


def payload_hash(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@transaction.atomic
def verify_and_apply_development_iap(
    *,
    couple: Couple,
    owner: User,
    platform: str,
    receipt_payload: dict,
    request_id: str = "",
) -> Subscription:
    if not user_is_partner_one(owner, couple):
        raise PermissionDenied("Only Partner 1 can attach billing to this couple.")
    if couple.status not in {Couple.Status.PENDING, Couple.Status.ACTIVE}:
        raise ValidationError({"couple": "Cannot attach billing to this couple."})

    verified = verify_development_iap_payload(platform=platform, payload=receipt_payload)
    event, created = SubscriptionEvent.objects.get_or_create(
        platform=platform,
        event_id=verified.event_id,
        defaults={
            "event_type": verified.event_type,
            "payload_hash": payload_hash(receipt_payload),
            "payload": receipt_payload,
        },
    )
    if not created and event.status == SubscriptionEvent.Status.PROCESSED and event.subscription_id:
        return event.subscription

    subscription = apply_verified_iap_payload(
        couple=couple,
        owner=owner,
        verified=verified,
    )
    event.subscription = subscription
    event.status = SubscriptionEvent.Status.PROCESSED
    event.processed_at = timezone.now()
    event.failure_reason = ""
    event.save(update_fields=["subscription", "status", "processed_at", "failure_reason", "updated_at"])
    record_audit_event(
        action="billing.iap_processed",
        actor=owner,
        target=subscription,
        request_id=request_id,
        metadata={"platform": platform, "event_id": verified.event_id, "event_type": verified.event_type},
    )
    from apps.profile_features.services import maybe_grant_referral_reward_from_subscription_event

    maybe_grant_referral_reward_from_subscription_event(subscription=subscription, event=event)
    return subscription


def apply_verified_iap_payload(*, couple: Couple, owner: User, verified: VerifiedIAPPayload) -> Subscription:
    app_account_token = verified.app_account_token or f"development:{verified.platform}:{owner.id}:{couple.id}"
    IAPPurchaseAccount.objects.get_or_create(
        platform=verified.platform,
        app_account_token=app_account_token,
        defaults={
            "user": owner,
            "couple": couple,
        },
    )
    is_ended_event = verified.event_type in ENDED_EVENT_TYPES or verified.revoked_at is not None
    status = Subscription.Status.ACTIVE if verified.is_active and not is_ended_event else Subscription.Status.EXPIRED
    if verified.revoked_at is not None:
        status = Subscription.Status.REVOKED

    subscription, _ = Subscription.objects.update_or_create(
        platform=verified.platform,
        original_transaction_id=verified.original_transaction_id,
        defaults={
            "couple": couple,
            "owner": owner,
            "product_id": verified.product_id,
            "latest_transaction_id": verified.latest_transaction_id,
            "status": status,
            "starts_at": verified.starts_at,
            "expires_at": verified.expires_at,
            "revoked_at": verified.revoked_at,
            "raw_latest_event": verified.raw_payload,
        },
    )
    sync_entitlement_from_subscription(subscription)
    return subscription


def sync_entitlement_from_subscription(subscription: Subscription) -> Entitlement:
    source = (
        Entitlement.Source.APPLE_IAP
        if subscription.platform == IAPPurchaseAccount.Platform.APPLE
        else Entitlement.Source.GOOGLE_IAP
    )
    entitlement, _ = Entitlement.objects.update_or_create(
        couple=subscription.couple,
        source=source,
        external_reference=subscription.original_transaction_id,
        defaults={
            "starts_at": subscription.starts_at,
            "expires_at": subscription.expires_at,
            "revoked_at": subscription.revoked_at
            if subscription.status in {Subscription.Status.REVOKED, Subscription.Status.CANCELED}
            else None,
        },
    )
    if subscription.status in {Subscription.Status.EXPIRED, Subscription.Status.REVOKED, Subscription.Status.CANCELED}:
        entitlement.expires_at = subscription.expires_at or timezone.now()
        if subscription.status == Subscription.Status.REVOKED:
            entitlement.revoked_at = subscription.revoked_at or timezone.now()
        entitlement.save(update_fields=["expires_at", "revoked_at", "updated_at"])
    return entitlement
