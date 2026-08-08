import pytest
from datetime import timedelta
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.tokens import hash_secret
from apps.pacts.documents import send_pact_document_emails
from apps.pacts.models import ClauseApproval, ClauseProposal, PactClause, PactVersion
from apps.pacts.models import PactDocument, PactDocumentDownloadToken
from tests.helpers import authenticated_client
from tests.test_private_responses import create_active_couple


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_one_partner_cannot_activate_pact_alone():
    partner_one, _partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]

    propose = partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")
    approval = partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    assert propose.status_code == 200
    assert approval.status_code == 201
    assert PactVersion.objects.get(id=pact["versions"][0]["id"]).status == PactVersion.Status.PROPOSED
    assert PactClause.objects.count() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_second_partner_approval_activates_live_immutable_version():
    partner_one, partner_two = create_active_couple()
    pact = create_pact(partner_one)
    version_id = pact["versions"][0]["id"]
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")

    partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    partner_two.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    version = PactVersion.objects.get(id=version_id)
    clause = PactClause.objects.get(version=version)
    assert version.status == PactVersion.Status.LIVE
    assert version.pact.live_version_id == version.id
    assert clause.text == "We agree to discuss finances every Sunday."

    edit_live = partner_one.patch(
        f"/api/v1/clause-proposals/{proposal_id}/",
        {"text": "Try editing live version."},
        content_type="application/json",
    )
    clause.refresh_from_db()
    assert edit_live.status_code == 400
    assert clause.text == "We agree to discuss finances every Sunday."


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_editing_proposal_invalidates_existing_approvals():
    partner_one, _partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")
    partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    edit = partner_one.patch(
        f"/api/v1/clause-proposals/{proposal_id}/",
        {"text": "We agree to discuss finances twice a month."},
        content_type="application/json",
    )

    approval = ClauseApproval.objects.get(proposal_id=proposal_id)
    proposal = ClauseProposal.objects.get(id=proposal_id)
    assert edit.status_code == 200
    assert proposal.revision == 2
    assert approval.invalidated_at is not None


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_repeated_same_partner_approval_is_idempotent_for_revision():
    partner_one, _partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")

    first = partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    second = partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    assert first.status_code == 201
    assert second.status_code == 201
    assert ClauseApproval.objects.filter(proposal_id=proposal_id).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_cross_couple_user_cannot_view_or_approve_pact():
    partner_one, _partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    outsider = authenticated_client("pact-outsider@example.com")
    outsider.post("/api/v1/couples/")

    read = outsider.get(f"/api/v1/pacts/{pact['id']}/")
    approve = outsider.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    assert read.status_code == 404
    assert approve.status_code == 404


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_live_pact_activation_generates_private_pdf_and_emails_both_partners():
    partner_one, partner_two = create_active_couple()
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]

    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")
    partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    partner_two.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")

    document = PactDocument.objects.get(version_id=pact["versions"][0]["id"])
    document.file.open("rb")
    try:
        pdf_bytes = document.file.read()
    finally:
        document.file.close()
    assert document.checksum_sha256
    assert document.byte_size == len(pdf_bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"We agree to discuss finances every Sunday." in pdf_bytes
    assert document.email_attempts == 1
    assert document.emailed_at is not None
    pact_emails = [email for email in mail.outbox if "Your Patto pact is live" in email.subject]
    assert len(pact_emails) == 2
    assert all(email.attachments[0][0] == document.filename for email in pact_emails)


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PACT_PDF_TOKEN_TTL_MINUTES=5)
def test_authenticated_expiring_pdf_download_link():
    partner_one, partner_two = create_active_couple()
    pact = activate_pact(partner_one, partner_two)
    version_id = pact["versions"][0]["id"]

    link_response = partner_one.post(f"/api/v1/pacts/{pact['id']}/versions/{version_id}/pdf-link/")
    download = partner_one.get(f"/api/v1/pact-pdfs/{link_response.json()['token']}/download/")

    assert link_response.status_code == 200
    assert link_response.json()["expires_in_minutes"] == 5
    assert download.status_code == 200
    assert download["Content-Type"] == "application/pdf"
    body = b"".join(download.streaming_content)
    assert body.startswith(b"%PDF-")


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_expired_and_cross_couple_pdf_downloads_are_denied():
    partner_one, partner_two = create_active_couple()
    pact = activate_pact(partner_one, partner_two)
    document = PactDocument.objects.get(version_id=pact["versions"][0]["id"])
    expired_raw_token = "expired-token"
    PactDocumentDownloadToken.objects.create(
        document=document,
        couple=document.couple,
        user=document.couple.members.get(role="partner_1").user,
        token_hash=hash_secret(expired_raw_token),
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    valid_link = partner_one.post(f"/api/v1/pacts/{pact['id']}/versions/{pact['versions'][0]['id']}/pdf-link/").json()
    outsider = authenticated_client("pact-pdf-outsider@example.com")
    outsider.post("/api/v1/couples/")

    expired = partner_one.get(f"/api/v1/pact-pdfs/{expired_raw_token}/download/")
    cross_couple = outsider.get(f"/api/v1/pact-pdfs/{valid_link['token']}/download/")

    assert expired.status_code == 403
    assert cross_couple.status_code == 403


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_email_retry_does_not_create_new_pact_version():
    partner_one, partner_two = create_active_couple()
    pact = activate_pact(partner_one, partner_two)
    document = PactDocument.objects.get(version_id=pact["versions"][0]["id"])

    send_pact_document_emails(document=document)
    document.refresh_from_db()

    assert document.email_attempts == 2
    assert PactVersion.objects.filter(pact_id=pact["id"]).count() == 1


def create_pact(client):
    response = client.post(
        "/api/v1/pacts/",
        {
            "title": "Money Pact",
            "manual_clauses": ["We agree to discuss finances every Sunday."],
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    return response.json()


def activate_pact(partner_one, partner_two):
    pact = create_pact(partner_one)
    proposal_id = pact["versions"][0]["clause_proposals"][0]["id"]
    partner_one.post(f"/api/v1/pacts/{pact['id']}/propose/")
    partner_one.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    partner_two.post(f"/api/v1/clause-proposals/{proposal_id}/approve/")
    return pact
