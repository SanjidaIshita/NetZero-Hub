from datetime import time, timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from recycling.models import Booking, CollectionSlot, Notification, Payment
from recycling.services import orchestrator
from recycling.services.exceptions import (
    ChangeNotAllowed,
    FeeNotAccepted,
    NotEligible,
    PaymentFailed,
    SlotUnavailable,
)

from .helpers import SeededMixin


class CreateBookingTests(SeededMixin, TestCase):
    def test_s2_standard_booking_is_free_confirmed_and_notified(self):
        slot = self.slot()
        with self.captureOnCommitCallbacks(execute=True):
            booking = orchestrator.create_booking(self.user, slot_id=slot.id, **self.details())

        booking.refresh_from_db()
        slot.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertTrue(booking.reference.startswith("RC-"))
        self.assertEqual(booking.fee, 0)
        self.assertEqual(booking.suburb, "Wollongong")  # filled from the service area
        self.assertEqual(slot.reserved, 1)
        self.assertFalse(Payment.objects.exists())
        notice = booking.notifications.get()
        self.assertEqual(notice.kind, Notification.Kind.CONFIRMATION)
        self.assertIn(self.provider.phone, notice.message)  # provider contact details included
        self.assertEqual(len(mail.outbox), 1)

    def test_s1_outside_service_area_is_rejected_and_recorded(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(NotEligible) as ctx:
                orchestrator.create_booking(self.user, slot_id=self.slot().id, **self.details(postcode="2000"))
        booking = Booking.objects.get(reference=ctx.exception.extra["booking_reference"])
        self.assertEqual(booking.status, Booking.Status.REJECTED)
        self.assertIn("outside", booking.rejection_reason)
        self.assertEqual(booking.notifications.get().kind, Notification.Kind.REJECTION)

    def test_unsupported_waste_type_is_rejected(self):
        with self.assertRaises(NotEligible) as ctx:
            orchestrator.create_booking(self.user, slot_id=self.slot().id, **self.details(waste_type=self.mattress))
        self.assertEqual(ctx.exception.extra["reason"], "waste_type_not_supported")

    def test_special_collection_requires_fee_acceptance(self):
        with self.assertRaises(FeeNotAccepted) as ctx:
            orchestrator.create_booking(self.user, slot_id=self.slot().id, **self.details(waste_type=self.ewaste))
        self.assertEqual(ctx.exception.extra["fee"], "25.00")
        self.assertFalse(Booking.objects.exists())

    def test_s3_special_large_booking_takes_payment(self):
        booking = orchestrator.create_booking(
            self.user,
            slot_id=self.slot().id,
            accept_fee=True,
            payment_token="tok_test",
            **self.details(waste_type=self.ewaste, quantity="LARGE"),
        )
        self.assertEqual(booking.fee, 55)  # 25 e-waste + 30 large-item surcharge
        self.assertEqual(booking.payment.status, Payment.Status.AUTHORISED)
        self.assertEqual(booking.payment.receipt_number, f"RCPT-{booking.reference}")

    def test_declined_payment_rolls_back_slot_reservation(self):
        slot = self.slot()
        with self.assertRaises(PaymentFailed):
            orchestrator.create_booking(
                self.user,
                slot_id=slot.id,
                accept_fee=True,
                payment_token="tok_decline",
                **self.details(waste_type=self.ewaste),
            )
        slot.refresh_from_db()
        self.assertEqual(slot.reserved, 0)
        self.assertFalse(Booking.objects.exists())

    def test_full_slot_cannot_be_booked(self):
        slot = self.slot()
        slot.reserved = slot.capacity
        slot.save()
        with self.assertRaises(SlotUnavailable):
            orchestrator.create_booking(self.user, slot_id=slot.id, **self.details())

    def test_same_day_slot_is_outside_booking_window(self):
        today_slot = CollectionSlot.objects.create(
            provider=self.provider, date=timezone.localdate(), start_time=time(23, 0), end_time=time(23, 30)
        )
        with self.assertRaises(SlotUnavailable):
            orchestrator.create_booking(self.user, slot_id=today_slot.id, **self.details())


class ChangeBookingTests(SeededMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.booking = orchestrator.create_booking(self.user, slot_id=self.slot(3).id, **self.details())

    def test_reschedule_moves_reservation(self):
        old, new = self.slot(3), self.slot(5, 1)
        orchestrator.reschedule_booking(self.booking, new.id)
        old.refresh_from_db()
        new.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.slot, new)
        self.assertEqual((old.reserved, new.reserved), (0, 1))

    def test_cancel_releases_slot(self):
        orchestrator.cancel_booking(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)
        self.assertEqual(self.slot(3).reserved, 0)
        with self.assertRaises(ChangeNotAllowed):
            orchestrator.cancel_booking(self.booking)

    def test_cancelling_paid_booking_refunds(self):
        paid = orchestrator.create_booking(
            self.user,
            slot_id=self.slot(4).id,
            accept_fee=True,
            payment_token="tok_test",
            **self.details(waste_type=self.ewaste),
        )
        orchestrator.cancel_booking(paid)
        paid.payment.refresh_from_db()
        self.assertEqual(paid.payment.status, Payment.Status.REFUNDED)

    def test_changes_blocked_inside_cutoff(self):
        self.booking.slot = self.make_slot_tomorrow_morning()
        self.booking.save()
        with self.assertRaises(ChangeNotAllowed):
            orchestrator.cancel_booking(self.booking)


class ProviderCallbackTests(SeededMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.booking = orchestrator.create_booking(self.user, slot_id=self.slot(3).id, **self.details())

    def test_collection_completed(self):
        orchestrator.collection_completed(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.COLLECTED)

    def test_s4_missed_collection_is_automatically_rescheduled_and_notified(self):
        missed_slot = self.booking.slot
        with self.captureOnCommitCallbacks(execute=True):
            orchestrator.collection_missed(self.booking, "Truck breakdown")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.RESCHEDULED)
        self.assertEqual(self.booking.missed_count, 1)
        self.assertGreater(self.booking.slot.date, missed_slot.date)
        notice = self.booking.notifications.first()
        self.assertEqual(notice.kind, Notification.Kind.MISSED_COLLECTION)
        self.assertIn("Truck breakdown", notice.message)
        statuses = list(self.booking.events.values_list("status", flat=True))
        self.assertEqual(statuses[-2:], ["MISSED", "RESCHEDULED"])


class ReminderTests(SeededMixin, TestCase):
    def test_reminder_sent_once_day_before(self):
        booking = orchestrator.create_booking(self.user, slot_id=self.slot(3).id, **self.details())
        day_before = booking.slot.date - timedelta(days=1)
        self.assertEqual(orchestrator.send_due_reminders(today=day_before), 1)
        self.assertEqual(orchestrator.send_due_reminders(today=day_before), 0)
        self.assertTrue(booking.notifications.filter(kind=Notification.Kind.REMINDER).exists())
