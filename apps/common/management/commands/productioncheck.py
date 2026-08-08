from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


INSECURE_SECRET_VALUES = {
    "",
    "change-me",
    "django-insecure-local-development-key",
}


class Command(BaseCommand):
    help = "Checks Patto-specific production readiness settings without contacting external providers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict-providers",
            action="store_true",
            help="Require OpenAI, SMTP, and IAP provider secrets to be configured.",
        )

    def handle(self, *args, **options):
        failures: list[str] = []
        warnings: list[str] = []

        if settings.DEBUG:
            failures.append("DJANGO_DEBUG must be false in production.")

        if settings.SECRET_KEY in INSECURE_SECRET_VALUES or len(settings.SECRET_KEY) < 32:
            failures.append("DJANGO_SECRET_KEY must be a strong non-default secret.")

        allowed_hosts = set(settings.ALLOWED_HOSTS)
        if not allowed_hosts:
            failures.append("DJANGO_ALLOWED_HOSTS must include production hostnames.")
        if "*" in allowed_hosts:
            failures.append("DJANGO_ALLOWED_HOSTS must not contain '*'.")
        localhost_hosts = {"localhost", "127.0.0.1", "api"}
        if allowed_hosts and allowed_hosts <= localhost_hosts:
            failures.append("DJANGO_ALLOWED_HOSTS cannot be only local development hosts.")

        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        insecure_cors = [origin for origin in cors_origins if not origin.startswith("https://")]
        if insecure_cors:
            failures.append("DJANGO_CORS_ALLOWED_ORIGINS must use https origins in production.")

        csrf_origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", [])
        insecure_csrf = [origin for origin in csrf_origins if not origin.startswith("https://")]
        if insecure_csrf:
            failures.append("DJANGO_CSRF_TRUSTED_ORIGINS must use https origins in production.")

        if not settings.SECURE_SSL_REDIRECT:
            failures.append("SECURE_SSL_REDIRECT must be enabled.")
        if not settings.SESSION_COOKIE_SECURE:
            failures.append("SESSION_COOKIE_SECURE must be enabled.")
        if not settings.CSRF_COOKIE_SECURE:
            failures.append("CSRF_COOKIE_SECURE must be enabled.")
        if getattr(settings, "SECURE_HSTS_SECONDS", 0) < 31536000:
            failures.append("SECURE_HSTS_SECONDS should be at least one year.")
        if settings.SECURE_PROXY_SSL_HEADER != ("HTTP_X_FORWARDED_PROTO", "https"):
            failures.append("SECURE_PROXY_SSL_HEADER must trust the deployment proxy's https header.")

        database_engine = settings.DATABASES["default"]["ENGINE"]
        if database_engine != "django.db.backends.postgresql":
            failures.append("Production database must use PostgreSQL.")

        if settings.EMAIL_BACKEND.endswith("locmem.EmailBackend"):
            failures.append("EMAIL_BACKEND cannot be locmem in production.")
        if getattr(settings, "EMAIL_HOST", "") in {"", "smtp.example.com"}:
            warnings.append("EMAIL_HOST is not configured for a real SMTP provider.")
        if getattr(settings, "DEFAULT_FROM_EMAIL", "").endswith("@example.com"):
            warnings.append("DEFAULT_FROM_EMAIL should be a verified sender domain.")

        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if not openai_key:
            warnings.append("OPENAI_API_KEY is empty; AI jobs will fail unless injected by the deployment platform.")

        if options["strict_providers"]:
            if not openai_key:
                failures.append("OPENAI_API_KEY is required with --strict-providers.")
            if not getattr(settings, "EMAIL_HOST_USER", "") or not getattr(settings, "EMAIL_HOST_PASSWORD", ""):
                failures.append("SMTP credentials are required with --strict-providers.")
            if not getattr(settings, "IAP_APPLE_SHARED_SECRET", "") and not getattr(settings, "IAP_GOOGLE_SERVICE_ACCOUNT_JSON", ""):
                failures.append("At least one IAP provider secret is required with --strict-providers.")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        if failures:
            for failure in failures:
                self.stderr.write(self.style.ERROR(f"ERROR: {failure}"))
            raise CommandError("production readiness checks failed")

        self.stdout.write(self.style.SUCCESS("production readiness checks passed"))
