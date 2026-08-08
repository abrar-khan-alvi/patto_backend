from django.contrib import admin

from apps.pacts.models import (
    ClauseApproval,
    ClauseProposal,
    Pact,
    PactClause,
    PactDocument,
    PactDocumentDownloadToken,
    PactSection,
    PactVersion,
)


class ClauseProposalInline(admin.TabularInline):
    model = ClauseProposal
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class PactClauseInline(admin.TabularInline):
    model = PactClause
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Pact)
class PactAdmin(admin.ModelAdmin):
    list_display = ("id", "couple", "title", "live_version", "created_by", "created_at")
    search_fields = ("id", "title", "couple__id", "created_by__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PactVersion)
class PactVersionAdmin(admin.ModelAdmin):
    list_display = ("pact", "version", "status", "proposed_by", "activated_at", "created_at")
    list_filter = ("status",)
    search_fields = ("pact__id", "couple__id")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ClauseProposalInline]


@admin.register(PactSection)
class PactSectionAdmin(admin.ModelAdmin):
    list_display = ("version", "title", "sort_order", "created_at")
    search_fields = ("version__id", "title")
    inlines = [PactClauseInline]


@admin.register(ClauseProposal)
class ClauseProposalAdmin(admin.ModelAdmin):
    list_display = ("version", "revision", "created_by", "created_at", "updated_at")
    search_fields = ("version__id", "text", "created_by__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClauseApproval)
class ClauseApprovalAdmin(admin.ModelAdmin):
    list_display = ("proposal", "user", "role", "proposal_revision", "approved_at", "invalidated_at")
    list_filter = ("role", "invalidated_at")
    search_fields = ("proposal__id", "user__email")
    readonly_fields = ("created_at",)


@admin.register(PactDocument)
class PactDocumentAdmin(admin.ModelAdmin):
    list_display = ("version", "filename", "checksum_sha256", "byte_size", "generated_at", "emailed_at", "email_attempts")
    search_fields = ("version__id", "checksum_sha256", "filename")
    readonly_fields = ("checksum_sha256", "byte_size", "generated_at", "emailed_at", "email_attempts", "created_at", "updated_at")


@admin.register(PactDocumentDownloadToken)
class PactDocumentDownloadTokenAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "expires_at", "used_at", "created_at")
    search_fields = ("document__id", "user__email")
    readonly_fields = ("token_hash", "created_at")
