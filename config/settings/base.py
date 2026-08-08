import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-development-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.couples",
    "apps.billing",
    "apps.topics",
    "apps.responses",
    "apps.ai",
    "apps.analysis",
    "apps.discussions",
    "apps.pacts",
    "apps.notifications",
    "apps.daily",
    "apps.insights",
    "apps.challenges",
    "apps.coach",
    "apps.conflicts",
    "apps.moments",
    "apps.profile_features",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "patto"),
        "USER": os.getenv("POSTGRES_USER", "patto"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "patto"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_STORE_RESPONSES = env_bool("OPENAI_STORE_RESPONSES", False)
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
IAP_APPLE_SHARED_SECRET = os.getenv("IAP_APPLE_SHARED_SECRET", "")
IAP_GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
AI_TOPIC_ANALYSIS_PROMPT_KEY = os.getenv("AI_TOPIC_ANALYSIS_PROMPT_KEY", "topic_analysis")
AI_FOLLOW_UP_PROMPT_KEY = os.getenv("AI_FOLLOW_UP_PROMPT_KEY", "follow_up_question")
AI_MONTHLY_INSIGHT_PROMPT_KEY = os.getenv("AI_MONTHLY_INSIGHT_PROMPT_KEY", "monthly_insight")
AI_COACH_PROMPT_KEY = os.getenv("AI_COACH_PROMPT_KEY", "coach")
AI_CONFLICT_BRIDGE_PROMPT_KEY = os.getenv("AI_CONFLICT_BRIDGE_PROMPT_KEY", "conflict_bridge")
AI_AUTO_DISPATCH_ANALYSIS = env_bool("AI_AUTO_DISPATCH_ANALYSIS", False)
AI_AUTO_DISPATCH_MONTHLY_INSIGHTS = env_bool("AI_AUTO_DISPATCH_MONTHLY_INSIGHTS", False)
MONTHLY_INSIGHT_MIN_REVEALED_DAYS = int(os.getenv("MONTHLY_INSIGHT_MIN_REVEALED_DAYS", "3"))

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.example.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@patto.app")

OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_REQUEST_WINDOW_MINUTES = int(os.getenv("OTP_REQUEST_WINDOW_MINUTES", "10"))
OTP_MAX_REQUESTS_PER_WINDOW = int(os.getenv("OTP_MAX_REQUESTS_PER_WINDOW", "3"))
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "15"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))
PARTNER_INVITATION_TTL_DAYS = int(os.getenv("PARTNER_INVITATION_TTL_DAYS", "7"))
PARTNER_INVITATION_URL_TEMPLATE = os.getenv(
    "PARTNER_INVITATION_URL_TEMPLATE",
    "https://app.patto.app/invitations/accept?token={token}",
)
PACT_PDF_TOKEN_TTL_MINUTES = int(os.getenv("PACT_PDF_TOKEN_TTL_MINUTES", "60"))
PACT_PDF_DOWNLOAD_URL_TEMPLATE = os.getenv(
    "PACT_PDF_DOWNLOAD_URL_TEMPLATE",
    "https://app.patto.app/pact-pdfs/{token}/download",
)
MOMENT_MEDIA_TOKEN_TTL_MINUTES = int(os.getenv("MOMENT_MEDIA_TOKEN_TTL_MINUTES", "30"))
MOMENT_MEDIA_DOWNLOAD_URL_TEMPLATE = os.getenv(
    "MOMENT_MEDIA_DOWNLOAD_URL_TEMPLATE",
    "https://app.patto.app/moment-media/{token}/download",
)

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", True)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.BearerTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Patto API",
    "DESCRIPTION": "Backend API for the Patto relationship agreement product.",
    "VERSION": "0.1.0",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}
