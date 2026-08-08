import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.http import FileResponse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.tokens import hash_secret
from apps.common.services import record_audit_event
from apps.couples.models import CoupleMember
from apps.couples.permissions import user_is_active_couple_member
from apps.pacts.models import PactDocument, PactDocumentDownloadToken, PactVersion
from apps.pacts.pdf import build_pact_pdf_bytes


def generate_pact_document_for_live_version(*, version: PactVersion) -> PactDocument:
    version = PactVersion.objects.select_related("pact", "couple").prefetch_related("clauses").get(id=version.id)
    if version.status != PactVersion.Status.LIVE:
        raise ValidationError({"version": "Only live pact versions can be exported as PDFs."})
    try:
        return version.document
    except PactDocument.DoesNotExist:
        pass

    pdf_bytes = build_pact_pdf_bytes(version=version)
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f"patto-pact-v{version.version}.pdf"
    document = PactDocument(
        pact=version.pact,
        version=version,
        couple=version.couple,
        filename=filename,
        checksum_sha256=checksum,
        byte_size=len(pdf_bytes),
        generated_at=timezone.now(),
    )
    document.file.save(filename, ContentFile(pdf_bytes), save=True)
    record_audit_event(
        action="pact_pdf.generated",
        actor=None,
        target=version,
        metadata={"document_id": str(document.id), "checksum_sha256": checksum},
    )
    return document


def generate_and_email_live_pact_pdf(*, version_id) -> PactDocument:
    version = PactVersion.objects.get(id=version_id)
    document = generate_pact_document_for_live_version(version=version)
    send_pact_document_emails(document=document)
    return document


def send_pact_document_emails(*, document: PactDocument) -> PactDocument:
    active_members = document.couple.members.filter(status=CoupleMember.Status.ACTIVE).select_related("user").order_by("role")
    for member in active_members:
        _, download_url = create_pact_document_download_token(document=document, user=member.user)
        email = EmailMessage(
            subject=f"Your Patto pact is live: {document.pact.title}",
            body=(
                "Your shared Patto pact is now live.\n\n"
                f"Download it here: {download_url}\n\n"
                "This link expires automatically. You can also request a new authenticated download link in the app."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[member.user.email],
        )
        document.file.open("rb")
        try:
            email.attach(document.filename, document.file.read(), "application/pdf")
        finally:
            document.file.close()
        email.send(fail_silently=False)
    document.email_attempts += 1
    document.emailed_at = timezone.now()
    document.save(update_fields=["email_attempts", "emailed_at", "updated_at"])
    record_audit_event(
        action="pact_pdf.emailed",
        actor=None,
        target=document.version,
        metadata={"document_id": str(document.id), "recipient_count": active_members.count()},
    )
    return document


def create_pact_document_download_token(*, document: PactDocument, user) -> tuple[str, str]:
    if not user_is_active_couple_member(user, document.couple):
        raise PermissionDenied("Only active couple members can download this pact PDF.")
    token = secrets.token_urlsafe(48)
    PactDocumentDownloadToken.objects.create(
        document=document,
        couple=document.couple,
        user=user,
        token_hash=hash_secret(token),
        expires_at=timezone.now() + timedelta(minutes=settings.PACT_PDF_TOKEN_TTL_MINUTES),
    )
    return token, settings.PACT_PDF_DOWNLOAD_URL_TEMPLATE.format(token=token)


def resolve_pact_document_download(*, token: str, user) -> PactDocument:
    download_token = (
        PactDocumentDownloadToken.objects.select_related("document", "couple", "user")
        .filter(token_hash=hash_secret(token))
        .first()
    )
    if download_token is None or download_token.expires_at <= timezone.now():
        raise PermissionDenied("This pact PDF download link is invalid or expired.")
    if download_token.user_id != user.id or not user_is_active_couple_member(user, download_token.couple):
        raise PermissionDenied("You cannot download this pact PDF.")
    download_token.used_at = timezone.now()
    download_token.save(update_fields=["used_at"])
    return download_token.document


def pact_document_file_response(*, document: PactDocument) -> FileResponse:
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.filename,
        content_type="application/pdf",
    )
