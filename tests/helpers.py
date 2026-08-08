import re

from django.core import mail
from django.test import Client


def authenticated_client(email: str) -> Client:
    client = Client()
    client.post(
        "/api/v1/auth/otp/request/",
        {"email": email, "purpose": "login"},
        content_type="application/json",
    )
    code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)
    response = client.post(
        "/api/v1/auth/otp/verify/",
        {"email": email, "purpose": "login", "code": code},
        content_type="application/json",
    )
    token = response.json()["tokens"]["access_token"]
    return Client(HTTP_AUTHORIZATION=f"Bearer {token}")
