import hashlib
import hmac

from django.conf import settings


def hash_secret(secret: str) -> str:
    return hmac.new(
        key=settings.SECRET_KEY.encode("utf-8"),
        msg=secret.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
