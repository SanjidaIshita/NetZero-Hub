"""Business rules for the Solar Panel Installation service (ORG-001)."""
import uuid
from datetime import timedelta

from django.utils import timezone

from .catalogue import ADD_ONS, ROOF_TYPES, SERVICE_ID, STOREYS, SYSTEM_SIZES, TIME_SLOTS, by_id
from .models import SolarRequest


def today():
    return timezone.localdate()


def available_dates(days_ahead=21):
    """Site assessments run Monday to Saturday, starting tomorrow."""
    start = today() + timedelta(days=1)
    days = (start + timedelta(days=i) for i in range(days_ahead))
    return [d for d in days if d.weekday() != 6]


def slot_capacity(day, slot):
    return slot["capacity"] if day.weekday() < 5 else slot["capacity"] // 2


def booked_count(day, slot_id):
    return SolarRequest.objects.filter(
        assessment_date=day, time_slot=slot_id, status__in=SolarRequest.ACTIVE_STATUSES
    ).count()


def slot_id_for(day, slot_id):
    return f"{day.isoformat()}|{slot_id}"


def availability():
    """Slots in the same shape the recycling SlotPicker uses: id, date, start_time, end_time, remaining."""
    slots = []
    for day in available_dates():
        for slot in TIME_SLOTS:
            remaining = slot_capacity(day, slot) - booked_count(day, slot["id"])
            if remaining > 0:
                slots.append({
                    "id": slot_id_for(day, slot["id"]),
                    "date": day.isoformat(),
                    "start_time": slot["start"],
                    "end_time": slot["end"],
                    "remaining": remaining,
                })
    return slots


def recommend_size(quarterly_usage_kwh):
    """About 4 peak sun hours a day in NSW, so size the system to the daily use."""
    if not quarterly_usage_kwh or quarterly_usage_kwh <= 0:
        return None
    daily = quarterly_usage_kwh / 91
    return next((s for s in SYSTEM_SIZES if daily <= s["dailyKwh"]), SYSTEM_SIZES[-1])


def price_breakdown(system_size, roof_type, storeys, add_ons):
    system = by_id(SYSTEM_SIZES, system_size)
    roof = by_id(ROOF_TYPES, roof_type)
    storey = by_id(STOREYS, storeys)
    lines = [{"item": system["name"], "amount": system["price"]}]
    if roof["surcharge"]:
        lines.append({"item": f"{roof['name']} roof mounting", "amount": roof["surcharge"]})
    if storey["surcharge"]:
        lines.append({"item": f"{storey['name']} access", "amount": storey["surcharge"]})
    for add_on_id in add_ons:
        add_on = by_id(ADD_ONS, add_on_id)
        lines.append({"item": add_on["name"], "amount": add_on["price"]})
    return lines


def new_reference():
    return f"{SERVICE_ID}-{timezone.localtime():%y%m%d}-{uuid.uuid4().hex[:5].upper()}"
