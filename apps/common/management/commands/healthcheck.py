from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = "Checks core runtime dependencies for container health checks."

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            raise CommandError(f"database unavailable: {exc.__class__.__name__}") from exc

        try:
            import redis

            redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1).ping()
        except Exception as exc:
            raise CommandError(f"redis unavailable: {exc.__class__.__name__}") from exc

        self.stdout.write(self.style.SUCCESS("ok"))
