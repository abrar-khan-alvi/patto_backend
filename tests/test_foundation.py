import uuid

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.common.services import record_audit_event


@pytest.mark.django_db
def test_user_uses_uuid_primary_key():
    user = User.objects.create_user(email="person@example.com", password="strong-password")

    assert isinstance(user.id, uuid.UUID)


def test_health_endpoint_includes_request_id_header():
    response = Client().get("/api/v1/health/", HTTP_X_REQUEST_ID="test-request-id")

    assert response["X-Request-ID"] == "test-request-id"
    assert response.json()["service"] == "patto-api"


@pytest.mark.django_db
def test_audit_event_creation_handles_authenticated_actor():
    user = User.objects.create_user(email="actor@example.com", password="strong-password")

    event = record_audit_event(action="foundation.test", actor=user, target=user, request_id="req-1")

    assert event.actor == user
    assert event.target_type == "User"
    assert event.target_id == str(user.id)
    assert event.request_id == "req-1"
