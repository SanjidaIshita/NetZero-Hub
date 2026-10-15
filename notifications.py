"""INotification adapter: e-mails the resident and keeps a copy of every notice."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from ..models import Notification

logger = logging.getLogger(__name__)
Kind = Notification.Kind


def _slot_text(booking):
    slot = booking.slot
    if slot is None:
        return "to be advised"
    return f"{slot.date:%A %d %B %Y}, between {slot.start_time:%H:%M} and {slot.end_time:%H:%M}"


def _provider_text(booking):
    p = booking.provider
    if p is None:
        return ""
    return f"\nYour collection provider: {p.name}\nPhone: {p.phone}\nEmail: {p.email}\n"


def _render(booking, kind, note):
    ref = booking.reference
    when = _slot_text(booking)
    waste = booking.waste_type.name
    greeting = f"Hi {booking.customer_name},\n\n"

    if kind == Kind.CONFIRMATION:
        fee = f"\nFee paid: ${booking.fee} (receipt {booking.payment.receipt_number})\n" if booking.fee > 0 else ""
        return (
            f"Recycling collection confirmed - {ref}",
            greeting + f"Your {waste} collection is confirmed for {when}.\n"
            f"Booking reference: {ref}\n"
            f"Please place your recyclables at the kerbside collection point before the window starts.\n"
            + fee + _provider_text(booking),
        )
    if kind == Kind.RESCHEDULED:
        return (
            f"Recycling collection rescheduled - {ref}",
            greeting + f"Your {waste} collection ({ref}) has been moved to {when}.\n" + _provider_text(booking),
        )
    if kind == Kind.CANCELLATION:
        refund = "\nAny fee you paid has been refunded.\n" if booking.fee > 0 else ""
        return (
            f"Recycling collection cancelled - {ref}",
            greeting + f"Your {waste} collection ({ref}) has been cancelled.\n" + refund,
        )
    if kind == Kind.REMINDER:
        return (
            f"Reminder: recycling collection tomorrow - {ref}",
            greeting + f"Reminder: your {waste} collection is on {when}.\n"
            f"Please have your recyclables at the collection point before the window starts.\n"
            + _provider_text(booking),
        )
    if kind == Kind.MISSED_COLLECTION:
        if booking.status == booking.Status.RESCHEDULED:
            outcome = f"We have automatically rescheduled it to {when}."
        else:
            outcome = "We will contact you to arrange a make-up collection."
        reason = f"\nReason reported: {note}" if note else ""
        return (
            f"Missed recycling collection - {ref}",
            greeting + f"Unfortunately your {waste} collection ({ref}) was missed.{reason}\n"
            f"{outcome}\n" + _provider_text(booking),
        )
    if kind == Kind.COLLECTED:
        return (
            f"Recycling collected - {ref}",
            greeting + f"Your {waste} has been collected. Thank you for recycling!\n",
        )
    if kind == Kind.REJECTION:
        return (
            f"Recycling collection request not accepted - {ref}",
            greeting + f"We could not accept your collection request ({ref}).\nReason: {booking.rejection_reason}\n",
        )
    raise ValueError(f"Unknown notification kind {kind}")


def notify(booking, kind, note=""):
    subject, message = _render(booking, kind, note)
    delivered = True
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [booking.customer_email])
    except Exception:  # a mail outage must not lose the booking; the notice stays recorded
        logger.exception("Failed to deliver %s notice for %s", kind, booking.reference)
        delivered = False
    return Notification.objects.create(
        booking=booking,
        kind=kind,
        recipient=booking.customer_email,
        subject=subject,
        message=message,
        delivered=delivered,
    )
