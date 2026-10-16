"""IProviderScheduling adapter.

The provider's collection timetable is held locally as CollectionSlot rows (kept up to
date by the provider or by `seed_data --slots-only`). To integrate a real provider API,
replace these functions with HTTP calls; the orchestrator does not need to change.
"""

from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from ..models import CollectionSlot, ServiceArea
from .exceptions import SlotUnavailable


def booking_window():
    rules = settings.RECYCLING
    today = timezone.localdate()
    return today + timedelta(days=rules["MIN_LEAD_DAYS"]), today + timedelta(days=rules["BOOKING_WINDOW_DAYS"])


def check_service_area(postcode):
    return ServiceArea.objects.select_related("provider").filter(postcode=(postcode or "").strip()).first()


def get_available_slots(provider, date_from=None, date_to=None):
    first, last = booking_window()
    date_from = max(date_from or first, first)
    date_to = min(date_to or last, last)
    return CollectionSlot.objects.filter(
        provider=provider,
        date__gte=date_from,
        date__lte=date_to,
        reserved__lt=F("capacity"),
    ).order_by("date", "start_time")


def reserve_collection(provider, slot_id):
    """Reserve one unit of capacity. Must run inside transaction.atomic()."""
    try:
        slot = CollectionSlot.objects.select_for_update().get(pk=slot_id, provider=provider)
    except CollectionSlot.DoesNotExist:
        raise SlotUnavailable("That collection slot is not offered for your area.")

    first, last = booking_window()
    if not first <= slot.date <= last:
        raise SlotUnavailable("That collection date is outside the bookable window.")
    if slot.reserved >= slot.capacity:
        raise SlotUnavailable("That slot has just been taken. Please choose another time.")

    CollectionSlot.objects.filter(pk=slot.pk).update(reserved=F("reserved") + 1)
    slot.refresh_from_db()
    return slot


def release_collection(slot):
    if slot is not None:
        CollectionSlot.objects.filter(pk=slot.pk, reserved__gt=0).update(reserved=F("reserved") - 1)


def schedule_make_up_collection(provider, after_date):
    """Reserve the earliest slot after a missed collection. Returns None if none is free."""
    earliest = max(after_date, timezone.localdate()) + timedelta(days=1)
    slot = (
        CollectionSlot.objects.select_for_update()
        .filter(provider=provider, date__gte=earliest, reserved__lt=F("capacity"))
        .order_by("date", "start_time")
        .first()
    )
    if slot is None:
        return None
    CollectionSlot.objects.filter(pk=slot.pk).update(reserved=F("reserved") + 1)
    slot.refresh_from_db()
    return slot
