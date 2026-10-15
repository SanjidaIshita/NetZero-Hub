"""BookingOrchestrator: composite operations from BRD Part C.5, Table 3.

Effect scenarios covered (BRD C.4):
  S1 Rejected            -> eligibility fails, booking persisted as REJECTED and resident notified
  S2 Standard, collected -> reserve slot, CONFIRMED, notify, later COLLECTED
  S3 Special/large       -> as S2 plus quote, fee acceptance and payment (paidFor(p, b))
  S4 Missed collection   -> MISSED, automatic make-up slot (RESCHEDULED), notify
Cancelling a paid booking refunds the payment (the gap the BRD's effect analysis identified).
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import Booking, BookingEvent, Notification, Payment
from . import eligibility, notifications, payment, webhooks
from . import provider as provider_api
from .exceptions import ChangeNotAllowed, FeeNotAccepted, NotEligible

Status = Booking.Status
Kind = Notification.Kind


def _record(booking, status, note=""):
    BookingEvent.objects.create(booking=booking, status=status, note=note[:255])


def _announce(booking, kind, event, note=""):
    """Notify the resident and publish outputs once the surrounding transaction commits."""

    def run():
        notifications.notify(booking, kind, note)
        webhooks.publish_output(booking, event)

    transaction.on_commit(run)


def _ensure_changeable(booking):
    if not booking.is_active:
        raise ChangeNotAllowed(f"A {booking.get_status_display().lower()} booking cannot be changed.")
    if not booking.can_change:
        hours = settings.RECYCLING["CHANGE_CUTOFF_HOURS"]
        raise ChangeNotAllowed(
            f"Bookings can only be changed or cancelled up to {hours} hours before the collection window."
        )


# --- checkAvailability --------------------------------------------------------------------


def check_availability(user, postcode, waste_type, date_from=None, date_to=None):
    area = eligibility.check(user, postcode, waste_type)
    slots = provider_api.get_available_slots(area.provider, date_from, date_to)
    return area, slots


def quote(waste_type, quantity):
    return payment.quote_fee(waste_type, quantity)


# --- createBooking ------------------------------------------------------------------------


def create_booking(user, *, slot_id, accept_fee=False, payment_token="", **details):
    """Create and confirm a booking. `details` are the WMS-002 service inputs."""
    waste_type = details["waste_type"]
    quantity = details.get("quantity", Booking.Quantity.SMALL)

    try:
        area = eligibility.check(user, details["postcode"], waste_type)
    except NotEligible as exc:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=user, status=Status.REJECTED, rejection_reason=exc.message[:255], **details
            )
            _record(booking, Status.REJECTED, exc.message)
            _announce(booking, Kind.REJECTION, "booking.rejected")
        exc.extra["booking_reference"] = booking.reference
        raise

    fee, breakdown = payment.quote_fee(waste_type, quantity)
    if fee > 0 and not accept_fee:
        raise FeeNotAccepted(
            f"This collection incurs a fee of ${fee}. Please accept the fee to continue.",
            fee=str(fee),
            breakdown=breakdown,
        )

    with transaction.atomic():
        slot = provider_api.reserve_collection(area.provider, slot_id)
        if not details.get("suburb"):
            details["suburb"] = area.suburb
        booking = Booking.objects.create(
            user=user, provider=area.provider, slot=slot, fee=fee, status=Status.PENDING, **details
        )
        _record(booking, Status.PENDING, f"Slot {slot} reserved with {area.provider.name}")

        if fee > 0:
            receipt = payment.authorise_payment(booking, fee, payment_token)
            _record(booking, Status.PENDING, f"Payment authorised, receipt {receipt.receipt_number}")

        booking.status = Status.CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.save(update_fields=["status", "confirmed_at", "updated_at"])
        _record(booking, Status.CONFIRMED, "Booking confirmed")
        _announce(booking, Kind.CONFIRMATION, "booking.confirmed")
    return booking


# --- rescheduleBooking / cancelBooking ----------------------------------------------------


def reschedule_booking(booking, slot_id):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("slot", "provider").get(pk=booking.pk)
        _ensure_changeable(booking)
        if booking.slot_id == slot_id:
            raise ChangeNotAllowed("The booking is already in that slot.")

        old_slot = booking.slot
        new_slot = provider_api.reserve_collection(booking.provider, slot_id)
        provider_api.release_collection(old_slot)

        booking.slot = new_slot
        booking.status = Status.CONFIRMED
        booking.reminder_sent_for = None
        booking.save(update_fields=["slot", "status", "reminder_sent_for", "updated_at"])
        _record(booking, Status.CONFIRMED, f"Rescheduled by resident from {old_slot} to {new_slot}")
        _announce(booking, Kind.RESCHEDULED, "booking.rescheduled")
    return booking


def cancel_booking(booking):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("slot").get(pk=booking.pk)
        _ensure_changeable(booking)

        provider_api.release_collection(booking.slot)
        note = "Cancelled by resident"
        paid = Payment.objects.filter(booking=booking, status=Payment.Status.AUTHORISED).first()
        if paid:
            payment.refund(paid)
            note += f"; payment {paid.receipt_number} refunded"

        booking.status = Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        _record(booking, Status.CANCELLED, note)
        _announce(booking, Kind.CANCELLATION, "booking.cancelled")
    return booking


# --- ICollectionStatus callbacks from the provider ---------------------------------------


def collection_completed(booking):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if not booking.is_active:
            raise ChangeNotAllowed(f"Cannot complete a {booking.get_status_display().lower()} booking.")
        booking.status = Status.COLLECTED
        booking.save(update_fields=["status", "updated_at"])
        _record(booking, Status.COLLECTED, "Provider reported collection completed")
        _announce(booking, Kind.COLLECTED, "booking.collected")
    return booking


def collection_missed(booking, reason=""):
    """Penalty clause: a missed collection is automatically rescheduled and the resident notified."""
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("slot", "provider").get(pk=booking.pk)
        if not booking.is_active:
            raise ChangeNotAllowed(f"Cannot report a {booking.get_status_display().lower()} booking as missed.")

        missed_slot = booking.slot
        booking.missed_count += 1
        _record(booking, Status.MISSED, f"Collection on {missed_slot} missed. {reason}".strip())

        make_up = provider_api.schedule_make_up_collection(booking.provider, missed_slot.date)
        if make_up is not None:
            booking.slot = make_up
            booking.status = Status.RESCHEDULED
            booking.reminder_sent_for = None
            _record(booking, Status.RESCHEDULED, f"Automatic make-up collection booked for {make_up}")
        else:
            booking.status = Status.MISSED
        booking.save(update_fields=["slot", "status", "missed_count", "reminder_sent_for", "updated_at"])
        _announce(booking, Kind.MISSED_COLLECTION, "booking.missed", reason)
    return booking


# --- reminders -----------------------------------------------------------------------------


def send_due_reminders(today=None):
    today = today or timezone.localdate()
    target = today + timedelta(days=settings.RECYCLING["REMINDER_DAYS_BEFORE"])
    due = (
        Booking.objects.filter(status__in=Booking.ACTIVE_STATUSES, slot__date=target)
        .exclude(reminder_sent_for=target)
        .select_related("slot", "provider", "waste_type")
    )
    sent = 0
    for booking in due:
        notifications.notify(booking, Kind.REMINDER)
        booking.reminder_sent_for = target
        booking.save(update_fields=["reminder_sent_for", "updated_at"])
        sent += 1
    return sent
