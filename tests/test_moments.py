from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, PngImagePlugin

from apps.accounts.tokens import hash_secret
from apps.couples.models import Couple
from apps.moments.models import Moment, MomentMedia, MomentMediaDownloadToken, MomentTopicLink
from apps.moments.services import archive_moments_for_couple
from apps.topics.models import Topic
from tests.helpers import authenticated_client


def image_upload(name="moment.png", size=(640, 480), metadata=True):
    output = BytesIO()
    image = Image.new("RGB", size, color="purple")
    if metadata:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("private_note", "strip me")
        image.save(output, format="PNG", pnginfo=pnginfo)
    else:
        image.save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def create_active_couple(prefix="moment"):
    partner_one = authenticated_client(f"{prefix}-p1@example.com")
    couple_id = partner_one.post("/api/v1/couples/").json()["id"]
    token = partner_one.post(
        f"/api/v1/couples/{couple_id}/invitations/",
        {"email": f"{prefix}-p2@example.com"},
        content_type="application/json",
    ).json()["token"]
    partner_two = authenticated_client(f"{prefix}-p2@example.com")
    partner_two.post(
        "/api/v1/couples/invitations/accept/",
        {"token": token},
        content_type="application/json",
    )
    return partner_one, partner_two


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_create_moment_and_link_builtin_topic():
    partner_one, partner_two = create_active_couple()
    topic = Topic.objects.first()

    response = partner_one.post(
        "/api/v1/moments/",
        {
            "title": "A small win",
            "body": "We handled a hard conversation gently.",
            "topic_ids": [str(topic.id)],
        },
        content_type="application/json",
    )
    partner_view = partner_two.get(f"/api/v1/moments/{response.json()['id']}/")

    assert response.status_code == 201
    assert response.json()["title"] == "A small win"
    assert MomentTopicLink.objects.filter(moment_id=response.json()["id"], topic=topic).exists()
    assert partner_view.status_code == 200


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_moment_media_upload_strips_metadata_and_generates_thumbnail(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    partner_one, _ = create_active_couple("moment-media")
    moment_id = partner_one.post("/api/v1/moments/", {"title": "Photo"}, content_type="application/json").json()["id"]

    response = partner_one.post(
        f"/api/v1/moments/{moment_id}/media/",
        {"file": image_upload()},
    )
    media = MomentMedia.objects.get(id=response.json()["id"])

    assert response.status_code == 201
    assert response.json()["metadata_removed"] is True
    assert media.file.name
    assert media.thumbnail.name
    assert media.thumbnail_width <= 512
    assert media.thumbnail_height <= 512
    media.file.open("rb")
    try:
        with Image.open(media.file) as stored:
            assert "private_note" not in stored.info
    finally:
        media.file.close()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_moment_media_signed_download_and_expiry(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    partner_one, _ = create_active_couple("moment-download")
    moment_id = partner_one.post("/api/v1/moments/", {"title": "Download"}, content_type="application/json").json()["id"]
    media_id = partner_one.post(f"/api/v1/moments/{moment_id}/media/", {"file": image_upload()}).json()["id"]

    link_response = partner_one.post(
        f"/api/v1/moment-media/{media_id}/download-link/",
        {"variant": "thumbnail"},
        content_type="application/json",
    )
    token = link_response.json()["token"]
    download = partner_one.get(f"/api/v1/moment-media/{token}/download/")
    expired_token = "expired-moment-token"
    media = MomentMedia.objects.get(id=media_id)
    MomentMediaDownloadToken.objects.create(
        media=media,
        couple=media.couple,
        user=media.uploaded_by,
        token_hash=hash_secret(expired_token),
        variant="original",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    expired = partner_one.get(f"/api/v1/moment-media/{expired_token}/download/")

    assert link_response.status_code == 200
    assert "moment-media" in link_response.json()["download_url"]
    assert download.status_code == 200
    assert expired.status_code == 403


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_moment_cross_couple_media_access_denied(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    partner_one, _ = create_active_couple("moment-cross")
    moment_id = partner_one.post("/api/v1/moments/", {"title": "Private"}, content_type="application/json").json()["id"]
    media_id = partner_one.post(f"/api/v1/moments/{moment_id}/media/", {"file": image_upload()}).json()["id"]
    link_response = partner_one.post(f"/api/v1/moment-media/{media_id}/download-link/", {"variant": "original"}, content_type="application/json")

    outsider = authenticated_client("moment-outsider@example.com")
    outsider.post("/api/v1/couples/")
    outsider_detail = outsider.get(f"/api/v1/moments/{moment_id}/")
    outsider_link = outsider.post(f"/api/v1/moment-media/{media_id}/download-link/", {"variant": "original"}, content_type="application/json")
    outsider_download = outsider.get(f"/api/v1/moment-media/{link_response.json()['token']}/download/")

    assert outsider_detail.status_code == 404
    assert outsider_link.status_code == 404
    assert outsider_download.status_code == 403


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_couple_archival_archives_moments_and_blocks_new_media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    partner_one, _ = create_active_couple("moment-archive")
    moment_id = partner_one.post("/api/v1/moments/", {"title": "Archive me"}, content_type="application/json").json()["id"]
    moment = Moment.objects.get(id=moment_id)

    archived_count = archive_moments_for_couple(couple=moment.couple)
    moment.couple.status = Couple.Status.ARCHIVED
    moment.couple.archived_at = timezone.now()
    moment.couple.save(update_fields=["status", "archived_at", "updated_at"])
    upload_response = partner_one.post(f"/api/v1/moments/{moment_id}/media/", {"file": image_upload()})
    detail_response = partner_one.get(f"/api/v1/moments/{moment_id}/")
    moment.refresh_from_db()

    assert archived_count == 1
    assert moment.status == Moment.Status.ARCHIVED
    assert moment.archived_at is not None
    assert upload_response.status_code == 403
    assert detail_response.status_code == 200
