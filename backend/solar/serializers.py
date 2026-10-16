from datetime import date

from rest_framework import serializers

from .catalogue import ADD_ONS, PROPERTY_TYPES, ROOF_TYPES, SERVICE_ID, STOREYS, SYSTEM_SIZES, TIME_SLOTS, by_id
from .models import SolarRequest
from .services import price_breakdown


def _ids(items):
    return [i["id"] for i in items]


class SolarRequestCreateSerializer(serializers.Serializer):
    """Inputs for a new solar installation request (ORG-001)."""

    customer_name = serializers.CharField(min_length=2, max_length=100)
    customer_email = serializers.EmailField()
    customer_phone = serializers.RegexField(r"^\+?[\d\s()-]{8,20}$", error_messages={"invalid": "Enter a valid phone number."})
    address_line = serializers.CharField(min_length=3, max_length=255)
    suburb = serializers.CharField(min_length=2, max_length=100)
    postcode = serializers.RegexField(r"^\d{4}$", error_messages={"invalid": "Enter a 4-digit postcode."})
    property_type = serializers.ChoiceField(choices=_ids(PROPERTY_TYPES))
    storeys = serializers.ChoiceField(choices=_ids(STOREYS))
    roof_type = serializers.ChoiceField(choices=_ids(ROOF_TYPES))
    quarterly_usage_kwh = serializers.IntegerField(help_text="Average quarterly electricity usage in kWh")
    system_size = serializers.ChoiceField(choices=_ids(SYSTEM_SIZES))
    add_ons = serializers.ListField(child=serializers.ChoiceField(choices=_ids(ADD_ONS)), required=False, default=list)
    slot_id = serializers.CharField(help_text='Site assessment slot from /solar/availability/, e.g. "2026-10-21|am"')
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_slot_id(self, value):
        try:
            day, slot = value.split("|")
            day = date.fromisoformat(day)
        except ValueError:
            raise serializers.ValidationError("Choose a site assessment date and time.")
        if not by_id(TIME_SLOTS, slot):
            raise serializers.ValidationError("Choose a site assessment date and time.")
        return value

    def validate_add_ons(self, value):
        return list(dict.fromkeys(value))  # remove duplicates, keep order


class SolarRequestSerializer(serializers.ModelSerializer):
    """The ORG-001 service output."""

    service_id = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    system = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    add_on_names = serializers.SerializerMethodField()
    assessment = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    price_lines = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = SolarRequest
        fields = [
            "service_id", "reference", "status", "status_label", "created_at", "updated_at",
            "customer_name", "customer_email", "customer_phone", "address", "installer",
            "property", "quarterly_usage_kwh", "system", "add_ons", "add_on_names",
            "assessment", "notes", "price_lines", "total_price", "can_cancel",
        ]

    def get_service_id(self, obj) -> str:
        return SERVICE_ID

    def get_system(self, obj) -> dict:
        s = by_id(SYSTEM_SIZES, obj.system_size) or {}
        return {"id": obj.system_size, "name": s.get("name", obj.system_size), "panels": s.get("panels")}

    def get_property(self, obj) -> dict:
        return {
            "type": (by_id(PROPERTY_TYPES, obj.property_type) or {}).get("name", obj.property_type),
            "storeys": (by_id(STOREYS, obj.storeys) or {}).get("name", obj.storeys),
            "roof": (by_id(ROOF_TYPES, obj.roof_type) or {}).get("name", obj.roof_type),
        }

    def get_add_on_names(self, obj) -> list:
        return [(by_id(ADD_ONS, a) or {}).get("name", a) for a in obj.add_ons]

    def get_assessment(self, obj) -> dict:
        slot = by_id(TIME_SLOTS, obj.time_slot) or {}
        return {"date": obj.assessment_date.isoformat(), "start_time": slot.get("start"), "end_time": slot.get("end")}

    def get_address(self, obj) -> dict:
        return {"address_line": obj.address_line, "suburb": obj.suburb, "postcode": obj.postcode}

    def get_price_lines(self, obj) -> list:
        return price_breakdown(obj.system_size, obj.roof_type, obj.storeys, obj.add_ons)

    def get_can_cancel(self, obj) -> bool:
        return obj.is_active
