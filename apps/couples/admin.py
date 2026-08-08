from django.contrib import admin

from apps.couples.models import Couple, CoupleMember, PartnerInvitation


class CoupleMemberInline(admin.TabularInline):
    model = CoupleMember
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Couple)
class CoupleAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_by", "activated_at", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "created_by__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [CoupleMemberInline]


@admin.register(PartnerInvitation)
class PartnerInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "couple", "invited_by", "expires_at", "accepted_at", "revoked_at")
    list_filter = ("accepted_at", "revoked_at")
    search_fields = ("email", "couple__id", "invited_by__email")
    readonly_fields = ("token_hash", "created_at", "updated_at")
