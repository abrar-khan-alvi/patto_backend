import uuid

from django.db import models


def pact_document_upload_path(instance, filename: str) -> str:
    return f"pacts/{instance.couple_id}/{instance.version_id}/{filename}"


class Pact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="pacts")
    title = models.CharField(max_length=180, default="Relationship Pact")
    live_version = models.OneToOneField(
        "pacts.PactVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="live_for_pact",
    )
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_pacts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.couple_id}:{self.title}"


class PactVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROPOSED = "proposed", "Proposed"
        LIVE = "live", "Live"
        SUPERSEDED = "superseded", "Superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pact = models.ForeignKey(Pact, on_delete=models.CASCADE, related_name="versions")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="pact_versions")
    version = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    based_on_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="derived_versions",
    )
    proposed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proposed_pact_versions",
    )
    proposed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pact", "version"], name="unique_pact_version_number"),
        ]
        indexes = [
            models.Index(fields=["couple", "status", "created_at"]),
            models.Index(fields=["pact", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.pact_id}:v{self.version}:{self.status}"


class PactSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PactVersion, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=180)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["version", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.version_id}:{self.title}"


class PactClause(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PactVersion, on_delete=models.CASCADE, related_name="clauses")
    section = models.ForeignKey(PactSection, null=True, blank=True, on_delete=models.SET_NULL, related_name="clauses")
    text = models.TextField()
    source_proposed_clause = models.ForeignKey(
        "analysis.ProposedClause",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pact_clauses",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["version", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.version_id}:clause:{self.sort_order}"


class ClauseProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PactVersion, on_delete=models.CASCADE, related_name="clause_proposals")
    source_proposed_clause = models.ForeignKey(
        "analysis.ProposedClause",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clause_proposals",
    )
    text = models.TextField()
    revision = models.PositiveSmallIntegerField(default=1)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_clause_proposals")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["version", "created_at"]),
            models.Index(fields=["revision"]),
        ]

    def __str__(self) -> str:
        return f"{self.version_id}:proposal:{self.revision}"


class ClauseApproval(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(ClauseProposal, on_delete=models.CASCADE, related_name="approvals")
    version = models.ForeignKey(PactVersion, on_delete=models.CASCADE, related_name="clause_approvals")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="clause_approvals")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="clause_approvals")
    role = models.CharField(max_length=20)
    proposal_revision = models.PositiveSmallIntegerField()
    approved_at = models.DateTimeField()
    invalidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["proposal", "user", "proposal_revision"], name="unique_clause_approval_per_revision"),
        ]
        indexes = [
            models.Index(fields=["version", "invalidated_at"]),
            models.Index(fields=["proposal", "invalidated_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.proposal_id}:{self.user_id}:r{self.proposal_revision}"


class PactDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pact = models.ForeignKey(Pact, on_delete=models.CASCADE, related_name="documents")
    version = models.OneToOneField(PactVersion, on_delete=models.CASCADE, related_name="document")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="pact_documents")
    file = models.FileField(upload_to=pact_document_upload_path)
    filename = models.CharField(max_length=255)
    checksum_sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveIntegerField()
    generated_at = models.DateTimeField()
    emailed_at = models.DateTimeField(null=True, blank=True)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["couple", "generated_at"]),
            models.Index(fields=["checksum_sha256"]),
        ]

    def __str__(self) -> str:
        return f"{self.version_id}:{self.filename}"


class PactDocumentDownloadToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(PactDocument, on_delete=models.CASCADE, related_name="download_tokens")
    couple = models.ForeignKey("couples.Couple", on_delete=models.CASCADE, related_name="pact_document_tokens")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="pact_document_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"]),
            models.Index(fields=["document", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.document_id}:{self.user_id}:{self.expires_at}"
