from django.contrib import admin

from apps.notifications.models import Device, Notification, NotificationDelivery, NotificationPreference


class NotificationDeliveryInline(admin.TabularInline):
    model = NotificationDelivery
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "name", "is_active", "revoked_at", "created_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__email", "token", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "enabled", "updated_at")
    list_filter = ("category", "enabled")
    search_fields = ("user__email",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "status", "title", "created_at")
    list_filter = ("category", "status")
    search_fields = ("user__email", "event_key", "title", "body")
    readonly_fields = ("data", "created_at", "updated_at")
    inlines = [NotificationDeliveryInline]


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "device", "status", "attempts", "sent_at", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("notification__event_key", "device__token", "provider_message_id")
    readonly_fields = ("created_at", "updated_at")
