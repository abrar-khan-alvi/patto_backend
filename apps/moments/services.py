import hashlib
import secrets
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.tokens import hash_secret
from apps.common.services import record_audit_event
from apps.couples.models import Couple
from apps.couples.permissions import user_is_active_couple_member
from apps.moments.models import Moment, MomentMedia, MomentMediaDownloadToken, MomentTopicLink
from apps.topics.models import CoupleTopic, Topic


ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
THUMBNAIL_SIZE = (512, 512)


def ensure_moment_member(*, user, couple: Couple) -> None:
    if not user_is_active_couple_member(user, couple):
        raise PermissionDenied("Only active couple members can manage moments.")


@transaction.atomic
def create_moment(*, user, title: str, body: str = "", occurred_on=None, topic_ids: list | None = None, custom_topic_ids: list | None = None, request_id: str = "") -> Moment:
    membership = user.couple_memberships.select_related("couple").filter(status="active").first()
    if membership is None:
        raise ValidationError({"couple": "Join an active couple before creating moments."})
    ensure_moment_member(user=user, couple=membership.couple)
    moment = Moment.objects.create(
        couple=membership.couple,
        created_by=user,
        title=title.strip()[:180] or "Moment",
        body=body.strip(),
        occurred_on=occurred_on,
    )
    link_moment_topics(moment=moment, topic_ids=topic_ids or [], custom_topic_ids=custom_topic_ids or [])
    record_audit_event(action="moment.created", actor=user, target=moment, request_id=request_id)
    return moment


def link_moment_topics(*, moment: Moment, topic_ids: list, custom_topic_ids: list) -> None:
    for topic in Topic.objects.filter(id__in=topic_ids):
        MomentTopicLink.objects.get_or_create(moment=moment, couple=moment.couple, topic=topic)
    for custom_topic in CoupleTopic.objects.filter(id__in=custom_topic_ids, couple=moment.couple):
        MomentTopicLink.objects.get_or_create(moment=moment, couple=moment.couple, custom_topic=custom_topic)


def normalize_image_upload(uploaded_file) -> tuple[bytes, str, int, int]:
    if uploaded_file.size > MAX_IMAGE_BYTES:
        raise ValidationError({"file": "Image is too large."})
    raw_bytes = uploaded_file.read()
    try:
        with Image.open(BytesIO(raw_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(raw_bytes)) as image:
            format_name = image.format
            if format_name not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError({"file": "Unsupported image format."})
            image = image.convert("RGB") if format_name in {"JPEG", "WEBP"} else image.convert("RGBA")
            output = BytesIO()
            save_format = "JPEG" if format_name == "JPEG" else "PNG"
            filename_ext = "jpg" if save_format == "JPEG" else "png"
            if save_format == "JPEG":
                image.save(output, format=save_format, quality=90, optimize=True)
            else:
                image.save(output, format=save_format, optimize=True)
            return output.getvalue(), filename_ext, image.width, image.height
    except UnidentifiedImageError as exc:
        raise ValidationError({"file": "Uploaded file is not a valid image."}) from exc


def build_thumbnail_bytes(image_bytes: bytes) -> tuple[bytes, int, int]:
    with Image.open(BytesIO(image_bytes)) as image:
        image.thumbnail(THUMBNAIL_SIZE)
        output = BytesIO()
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        image.save(output, format="PNG", optimize=True)
        return output.getvalue(), image.width, image.height


@transaction.atomic
def upload_moment_media(*, moment: Moment, user, uploaded_file, request_id: str = "") -> MomentMedia:
    moment = Moment.objects.select_for_update().select_related("couple").get(id=moment.id)
    ensure_moment_member(user=user, couple=moment.couple)
    if moment.status == Moment.Status.ARCHIVED:
        raise ValidationError({"moment": "Archived moments cannot receive new media."})
    image_bytes, extension, width, height = normalize_image_upload(uploaded_file)
    thumbnail_bytes, thumb_width, thumb_height = build_thumbnail_bytes(image_bytes)
    checksum = hashlib.sha256(image_bytes).hexdigest()
    media = MomentMedia(
        moment=moment,
        couple=moment.couple,
        uploaded_by=user,
        filename=f"{uploaded_file.name.rsplit('.', 1)[0]}.{extension}",
        content_type="image/jpeg" if extension == "jpg" else "image/png",
        byte_size=len(image_bytes),
        width=width,
        height=height,
        thumbnail_width=thumb_width,
        thumbnail_height=thumb_height,
        checksum_sha256=checksum,
        metadata_removed=True,
    )
    media.file.save(media.filename, ContentFile(image_bytes), save=False)
    media.thumbnail.save(f"{media.id}-thumb.png", ContentFile(thumbnail_bytes), save=False)
    media.save()
    record_audit_event(action="moment_media.uploaded", actor=user, target=moment, request_id=request_id, metadata={"media_id": str(media.id), "metadata_removed": True})
    return media


def create_moment_media_download_token(*, media: MomentMedia, user, variant: str = "original") -> tuple[str, str]:
    if variant not in {"original", "thumbnail"}:
        raise ValidationError({"variant": "Variant must be original or thumbnail."})
    if not user_is_active_couple_member(user, media.couple):
        raise PermissionDenied("Only active couple members can access moment media.")
    token = secrets.token_urlsafe(48)
    MomentMediaDownloadToken.objects.create(
        media=media,
        couple=media.couple,
        user=user,
        token_hash=hash_secret(token),
        variant=variant,
        expires_at=timezone.now() + timedelta(minutes=settings.MOMENT_MEDIA_TOKEN_TTL_MINUTES),
    )
    return token, settings.MOMENT_MEDIA_DOWNLOAD_URL_TEMPLATE.format(token=token)


def resolve_moment_media_download(*, token: str, user) -> MomentMediaDownloadToken:
    download_token = MomentMediaDownloadToken.objects.select_related("media", "couple", "user").filter(token_hash=hash_secret(token)).first()
    if download_token is None or download_token.expires_at <= timezone.now():
        raise PermissionDenied("This moment media link is invalid or expired.")
    if download_token.user_id != user.id or not user_is_active_couple_member(user, download_token.couple):
        raise PermissionDenied("You cannot download this moment media.")
    download_token.used_at = timezone.now()
    download_token.save(update_fields=["used_at"])
    return download_token


def moment_media_file_response(*, download_token: MomentMediaDownloadToken) -> FileResponse:
    media = download_token.media
    field = media.thumbnail if download_token.variant == "thumbnail" else media.file
    return FileResponse(field.open("rb"), as_attachment=True, filename=media.filename, content_type=media.content_type)


@transaction.atomic
def archive_moments_for_couple(*, couple: Couple) -> int:
    now = timezone.now()
    return Moment.objects.filter(couple=couple, archived_at__isnull=True).update(status=Moment.Status.ARCHIVED, archived_at=now)
