import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


SECURE_PRODUCTION_OVERRIDES = {
    "DEBUG": False,
    "SECRET_KEY": "prod-secret-key-that-is-long-enough-for-tests",
    "ALLOWED_HOSTS": ["api.patto.app"],
    "CORS_ALLOWED_ORIGINS": ["https://app.patto.app"],
    "CSRF_TRUSTED_ORIGINS": ["https://app.patto.app"],
    "SECURE_SSL_REDIRECT": True,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_HSTS_SECONDS": 31536000,
    "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "patto",
        }
    },
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    "EMAIL_HOST": "smtp.mailprovider.test",
    "DEFAULT_FROM_EMAIL": "no-reply@patto.app",
}

STRICT_PROVIDER_MISSING_OVERRIDES = {
    **SECURE_PRODUCTION_OVERRIDES,
    "OPENAI_API_KEY": "",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "IAP_APPLE_SHARED_SECRET": "",
    "IAP_GOOGLE_SERVICE_ACCOUNT_JSON": "",
}


@pytest.mark.django_db
@override_settings(**SECURE_PRODUCTION_OVERRIDES)
def test_productioncheck_passes_for_secure_required_settings():
    call_command("productioncheck")


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    SECRET_KEY="change-me",
    ALLOWED_HOSTS=["localhost", "127.0.0.1"],
    CORS_ALLOWED_ORIGINS=["http://localhost:3000"],
    CSRF_TRUSTED_ORIGINS=["http://localhost:3000"],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    SECURE_HSTS_SECONDS=0,
    SECURE_PROXY_SSL_HEADER=None,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
def test_productioncheck_fails_for_local_development_settings():
    with pytest.raises(CommandError):
        call_command("productioncheck")


@pytest.mark.django_db
@override_settings(**STRICT_PROVIDER_MISSING_OVERRIDES)
def test_productioncheck_strict_provider_mode_requires_provider_secrets():
    with pytest.raises(CommandError):
        call_command("productioncheck", "--strict-providers")
