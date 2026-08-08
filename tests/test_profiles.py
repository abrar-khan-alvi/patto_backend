from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from PIL import Image

from apps.accounts.models import User, UserProfile
from tests.helpers import authenticated_client as make_authenticated_client


def tiny_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def authenticated_client():
    return make_authenticated_client("person@example.com")


@pytest.mark.django_db
def test_profile_is_created_for_new_user():
    user = User.objects.create_user(email="profile@example.com")

    assert UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_me_endpoint_returns_private_profile(authenticated_client):
    response = authenticated_client.get("/api/v1/me/")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "person@example.com"
    assert body["display_name"] == ""
    assert body["preferred_language"] == "en"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_me_endpoint_updates_profile_and_user_language(authenticated_client):
    response = authenticated_client.patch(
        "/api/v1/me/",
        {
            "display_name": "Abrar",
            "pronouns": "he/him",
            "preferred_language": "bn",
            "timezone": "Asia/Dhaka",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Abrar"
    assert body["timezone"] == "Asia/Dhaka"
    user = User.objects.get(email="person@example.com")
    assert user.preferred_language == "bn"
    assert user.timezone == "Asia/Dhaka"


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_avatar_upload_validates_image(authenticated_client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path

    invalid = SimpleUploadedFile("avatar.txt", b"not-image", content_type="text/plain")
    invalid_response = authenticated_client.post("/api/v1/me/avatar/", {"avatar": invalid})
    assert invalid_response.status_code == 400

    image = SimpleUploadedFile("avatar.png", tiny_png(), content_type="image/png")
    response = authenticated_client.post("/api/v1/me/avatar/", {"avatar": image})

    assert response.status_code == 200
    assert response.json()["avatar"].endswith(".png")

    delete_response = authenticated_client.delete("/api/v1/me/avatar/")
    assert delete_response.status_code == 204
    assert User.objects.get(email="person@example.com").profile.avatar == ""
