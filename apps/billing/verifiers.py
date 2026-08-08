from dataclasses import dataclass
from datetime import UTC, datetime

from django.utils import timezone
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class VerifiedIAPPayload:
    platform: str
    event_id: str
    event_type: str
    product_id: str
    original_transaction_id: str
    latest_transaction_id: str
    starts_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    app_account_token: str
    raw_payload: dict

    @property
    def is_active(self) -> bool:
        now = timezone.now()
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return True
        return self.expires_at > now


def verify_development_iap_payload(*, platform: str, payload: dict) -> VerifiedIAPPayload:
    required = [
        "event_id",
        "event_type",
        "product_id",
        "original_transaction_id",
        "latest_transaction_id",
        "starts_at",
    ]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValidationError({"receipt": f"Missing required development IAP fields: {', '.join(missing)}."})

    return VerifiedIAPPayload(
        platform=platform,
        event_id=str(payload["event_id"]),
        event_type=str(payload["event_type"]),
        product_id=str(payload["product_id"]),
        original_transaction_id=str(payload["original_transaction_id"]),
        latest_transaction_id=str(payload["latest_transaction_id"]),
        starts_at=parse_datetime(payload["starts_at"], "starts_at"),
        expires_at=parse_optional_datetime(payload.get("expires_at"), "expires_at"),
        revoked_at=parse_optional_datetime(payload.get("revoked_at"), "revoked_at"),
        app_account_token=str(payload.get("app_account_token", "")),
        raw_payload=payload,
    )


def parse_optional_datetime(value, field_name: str):
    if not value:
        return None
    return parse_datetime(value, field_name)


def parse_datetime(value, field_name: str):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=UTC)
    return parsed
