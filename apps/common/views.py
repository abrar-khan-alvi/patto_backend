from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def _check_database() -> dict[str, str]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": exc.__class__.__name__}


def _check_redis() -> dict[str, str]:
    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": exc.__class__.__name__}


def health_view(request):
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    healthy = all(item["status"] == "ok" for item in checks.values())
    return JsonResponse(
        {
            "status": "ok" if healthy else "degraded",
            "service": "patto-api",
            "checks": checks,
        },
        status=200 if healthy else 503,
    )
