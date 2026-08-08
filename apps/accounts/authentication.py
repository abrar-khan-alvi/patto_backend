from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import AuthSession
from apps.accounts.tokens import hash_secret


class BearerTokenAuthentication(BaseAuthentication):
    keyword = b"Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth:
            return None
        if auth[0] != self.keyword or len(auth) != 2:
            raise AuthenticationFailed("Invalid authorization header.")

        token_hash = hash_secret(auth[1].decode("utf-8"))
        session = (
            AuthSession.objects.select_related("user")
            .filter(access_token_hash=token_hash, revoked_at__isnull=True)
            .first()
        )
        if session is None or session.access_expires_at <= timezone.now():
            raise AuthenticationFailed("Access token expired or invalid.")
        if not session.user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        request.auth_session = session
        return (session.user, session)
