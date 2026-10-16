from django.contrib import admin

from .models import SolarRequest


@admin.register(SolarRequest)
class SolarRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "status", "customer_name", "suburb", "system_size", "assessment_date", "time_slot", "total_price")
    list_filter = ("status", "system_size", "roof_type", "assessment_date")
    search_fields = ("reference", "customer_name", "customer_email", "address_line", "suburb", "postcode")
    readonly_fields = ("reference", "created_at", "updated_at")
