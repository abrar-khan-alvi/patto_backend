import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from apps.accounts.models import AuthSession, EmailOTP, User
from apps.accounts.tokens import hash_secret
from apps.common.services import record_audit_event


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_at: object
    refresh_expires_at: object


def normalize_email(email: str) -> str:
    return User.objects.normalize_email(email).lower()


def create_or_update_user(*, email: str, preferred_language: str = "en", timezone_name: str = "UTC") -> User:
    normalized = normalize_email(email)
    user, created = User.objects.get_or_create(
        email=normalized,
        defaults={
            "preferred_language": preferred_language,
            "timezone": timezone_name,
            "is_active": True,
        },
    )
    if not created:
        changed = False
        if preferred_language and user.preferred_language != preferred_language:
            user.preferred_language = preferred_language
            changed = True
        if timezone_name and user.timezone != timezone_name:
            user.timezone = timezone_name
            changed = True
        if changed:
            user.save(update_fields=["preferred_language", "timezone", "updated_at"])
    return user


def send_otp(*, email: str, purpose: str) -> None:
    normalized = normalize_email(email)
    now = timezone.now()
    window_start = now - timedelta(minutes=settings.OTP_REQUEST_WINDOW_MINUTES)
    recent_count = EmailOTP.objects.filter(
        email=normalized,
        purpose=purpose,
        created_at__gte=window_start,
    ).count()
    if recent_count >= settings.OTP_MAX_REQUESTS_PER_WINDOW:
        raise Throttled(detail="Too many OTP requests. Please wait before trying again.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    EmailOTP.objects.create(
        email=normalized,
        purpose=purpose,
        code_hash=hash_secret(code),
        expires_at=now + timedelta(minutes=settings.OTP_TTL_MINUTES),
    )
    send_mail(
        subject="Your Patto verification code",
        message=f"Your Patto verification code is {code}. It expires in {settings.OTP_TTL_MINUTES} minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalized],
        fail_silently=False,
    )


@transaction.atomic
def verify_otp_and_issue_tokens(*, email: str, code: str, purpose: str, request_id: str = "") -> tuple[User, TokenPair]:
    normalized = normalize_email(email)
    now = timezone.now()
    otp = (
        EmailOTP.objects.select_for_update()
        .filter(email=normalized, purpose=purpose, consumed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise ValidationError({"code": "Invalid or expired OTP."})
    if otp.expires_at <= now:
        raise ValidationError({"code": "Invalid or expired OTP."})
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise Throttled(detail="Too many OTP attempts. Please request a new code.")

    otp.attempts += 1
    if otp.code_hash != hash_secret(code):
        otp.save(update_fields=["attempts"])
        raise ValidationError({"code": "Invalid or expired OTP."})

    otp.consumed_at = now
    otp.save(update_fields=["attempts", "consumed_at"])
    user = create_or_update_user(email=normalized)
    if user.email_verified_at is None:
        user.email_verified_at = now
        user.save(update_fields=["email_verified_at", "updated_at"])

    tokens = create_auth_session(user=user)
    record_audit_event(action="auth.otp_verified", actor=user, target=user, request_id=request_id)
    return user, tokens


def create_auth_session(*, user: User) -> TokenPair:
    access_token = secrets.token_urlsafe(48)
    refresh_token = secrets.token_urlsafe(64)
    now = timezone.now()
    access_expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    AuthSession.objects.create(
        user=user,
        access_token_hash=hash_secret(access_token),
        refresh_token_hash=hash_secret(refresh_token),
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


@transaction.atomic
def rotate_refresh_token(*, refresh_token: str) -> TokenPair:
    now = timezone.now()
    session = (
        AuthSession.objects.select_for_update()
        .filter(refresh_token_hash=hash_secret(refresh_token), revoked_at__isnull=True)
        .first()
    )
    if session is None or session.refresh_expires_at <= now:
        raise ValidationError({"refresh_token": "Refresh token expired or invalid."})

    session.revoked_at = now
    session.save(update_fields=["revoked_at", "updated_at"])
    return create_auth_session(user=session.user)


def revoke_session(*, session: AuthSession, request_id: str = "") -> None:
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at", "updated_at"])
        record_audit_event(action="auth.logout", actor=session.user, target=session.user, request_id=request_id)
