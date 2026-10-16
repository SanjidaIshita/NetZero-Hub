from django.contrib import admin

from .models import SolarRequest, SolarRequestEvent


class SolarRequestEventInline(admin.TabularInline):
    model = SolarRequestEvent
    extra = 0
    readonly_fields = ("status", "note", "actor", "created_at")
    can_delete = False


@admin.register(SolarRequest)
class SolarRequestAdmin(admin.ModelAdmin):
    inlines = [SolarRequestEventInline]
    list_display = ("reference", "status", "customer_name", "suburb", "system_size", "assessment_date", "time_slot", "total_price")
    list_filter = ("status", "system_size", "roof_type", "assessment_date")
    search_fields = ("reference", "customer_name", "customer_email", "address_line", "suburb", "postcode")
    readonly_fields = ("reference", "created_at", "updated_at")
