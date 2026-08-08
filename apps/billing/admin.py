from django.contrib import admin

from apps.billing.models import IAPPurchaseAccount, Subscription, SubscriptionEvent


@admin.register(IAPPurchaseAccount)
class IAPPurchaseAccountAdmin(admin.ModelAdmin):
    list_display = ("platform", "user", "couple", "app_account_token", "created_at")
    list_filter = ("platform",)
    search_fields = ("user__email", "couple__id", "app_account_token")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("platform", "product_id", "owner", "couple", "status", "expires_at")
    list_filter = ("platform", "status")
    search_fields = ("owner__email", "couple__id", "original_transaction_id", "latest_transaction_id")
    readonly_fields = ("created_at", "updated_at", "raw_latest_event")


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ("platform", "event_id", "event_type", "status", "processed_at", "created_at")
    list_filter = ("platform", "event_type", "status")
    search_fields = ("event_id", "subscription__original_transaction_id")
    readonly_fields = ("payload_hash", "payload", "created_at", "updated_at")
