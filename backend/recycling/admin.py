from django.contrib import admin

from .models import (
    Booking,
    BookingEvent,
    CollectionSlot,
    Notification,
    Payment,
    Provider,
    ServiceArea,
    WasteType,
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")
    filter_horizontal = ("waste_types",)


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("postcode", "suburb", "provider")
    search_fields = ("postcode", "suburb")


@admin.register(WasteType)
class WasteTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_special", "base_fee", "active")
    list_editable = ("active",)


@admin.register(CollectionSlot)
class CollectionSlotAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "provider", "reserved", "capacity")
    list_filter = ("provider", "date")


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ("status", "note", "created_at")


class NotificationInline(admin.TabularInline):
    model = Notification
    extra = 0
    readonly_fields = ("kind", "recipient", "subject", "delivered", "created_at")
    exclude = ("message",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer_name", "postcode", "waste_type", "slot", "status", "fee")
    list_filter = ("status", "waste_type", "provider")
    search_fields = ("reference", "customer_name", "customer_email", "postcode")
    readonly_fields = ("reference", "created_at", "updated_at", "confirmed_at")
    inlines = [BookingEventInline, NotificationInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "booking", "amount", "status", "created_at")
