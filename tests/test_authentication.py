import re

import pytest
from django.core import mail
from django.test import Client, override_settings

from apps.accounts.models import AuthSession, EmailOTP, User
from apps.accounts.tokens import hash_secret


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_register_sends_hashed_email_verification_otp():
    response = Client().post(
        "/api/v1/auth/register/",
        {
            "email": "Person@Example.com",
            "preferred_language": "en",
            "timezone": "Asia/Dhaka",
        },
        content_type="application/json",
    )

    assert response.status_code == 202
    assert User.objects.filter(email="person@example.com").exists()
    assert len(mail.outbox) == 1

    code = re.search(r"\b\d{6}\b", mail.outbox[0].body).group(0)
    otp = EmailOTP.objects.get(email="person@example.com")
    assert otp.code_hash == hash_secret(code)
    assert otp.code_hash != code


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_verify_otp_consumes_code_and_issues_tokens():
    client = Client()
    client.post(
        "/api/v1/auth/register/",
        {"email": "person@example.com"},
        content_type="application/json",
    )
    code = re.search(r"\b\d{6}\b", mail.outbox[0].body).group(0)

    response = client.post(
        "/api/v1/auth/otp/verify/",
        {
            "email": "person@example.com",
            "purpose": "email_verification",
            "code": code,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tokens"]["token_type"] == "Bearer"
    assert AuthSession.objects.filter(user__email="person@example.com", revoked_at__isnull=True).exists()
    assert EmailOTP.objects.get(email="person@example.com").consumed_at is not None

    second_response = client.post(
        "/api/v1/auth/otp/verify/",
        {
            "email": "person@example.com",
            "purpose": "email_verification",
            "code": code,
        },
        content_type="application/json",
    )
    assert second_response.status_code == 400


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_refresh_rotates_session_and_logout_revokes_access_token():
    client = Client()
    client.post(
        "/api/v1/auth/otp/request/",
        {"email": "person@example.com", "purpose": "login"},
        content_type="application/json",
    )
    code = re.search(r"\b\d{6}\b", mail.outbox[0].body).group(0)
    verify_response = client.post(
        "/api/v1/auth/otp/verify/",
        {"email": "person@example.com", "purpose": "login", "code": code},
        content_type="application/json",
    )
    original_refresh = verify_response.json()["tokens"]["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh_token": original_refresh},
        content_type="application/json",
    )

    assert refresh_response.status_code == 200
    assert AuthSession.objects.filter(revoked_at__isnull=False).count() == 1

    new_access = refresh_response.json()["tokens"]["access_token"]
    logout_response = client.post(
        "/api/v1/auth/logout/",
        HTTP_AUTHORIZATION=f"Bearer {new_access}",
    )

    assert logout_response.status_code == 204
    assert AuthSession.objects.filter(revoked_at__isnull=True).count() == 0
