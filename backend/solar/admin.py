from django.contrib import admin

from .models import SolarPayment, SolarRequest, SolarRequestEvent


class SolarRequestEventInline(admin.TabularInline):
    model = SolarRequestEvent
    extra = 0
    readonly_fields = ("status", "note", "actor", "created_at")
    can_delete = False


class SolarPaymentInline(admin.TabularInline):
    model = SolarPayment
    extra = 0
    readonly_fields = ("receipt_number", "kind", "amount", "card_brand", "card_last4", "created_at")
    can_delete = False


@admin.register(SolarRequest)
class SolarRequestAdmin(admin.ModelAdmin):
    inlines = [SolarPaymentInline, SolarRequestEventInline]
    list_display = ("reference", "status", "customer_name", "suburb", "system_size", "assessment_date", "time_slot", "total_price", "payment_status", "amount_paid")
    list_filter = ("status", "payment_status", "system_size", "roof_type", "assessment_date")
    search_fields = ("reference", "customer_name", "customer_email", "address_line", "suburb", "postcode")
    readonly_fields = ("reference", "amount_paid", "payment_status", "created_at", "updated_at")
