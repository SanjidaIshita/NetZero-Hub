"""Domain model for WMS-002 Recycling Collection Scheduling.

Objects of interest follow BRD Part C.4: booking b, resident r, collection slot d
and payment p, plus the provider that owns the collection timetable.
"""

import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid misreading


class Provider(models.Model):
    """Waste Service Provider: owns the collection timetable, vehicles and crews."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    website = models.URLField(blank=True)
    api_key = models.CharField(
        max_length=64,
        unique=True,
        help_text="Key the provider sends in X-Provider-Key when reporting collection status.",
    )
    waste_types = models.ManyToManyField("WasteType", related_name="providers", blank=True)

    def __str__(self):
        return self.name


class ServiceArea(models.Model):
    postcode = models.CharField(max_length=4, unique=True)
    suburb = models.CharField(max_length=100)
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="service_areas")

    class Meta:
        ordering = ["postcode"]

    def __str__(self):
        return f"{self.postcode} {self.suburb}"


class WasteType(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    accepted_items = models.TextField(blank=True, help_text="Guidance shown to residents.")
    is_special = models.BooleanField(
        default=False, help_text="Special collections are chargeable (standard recycling is free)."
    )
    base_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class CollectionSlot(models.Model):
    """A time window in the provider's collection timetable with limited capacity."""

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField(default=20)
    reserved = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "date", "start_time"], name="uniq_provider_slot"),
        ]
        indexes = [models.Index(fields=["provider", "date"])]

    def __str__(self):
        return f"{self.date} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    @property
    def remaining(self):
        return max(self.capacity - self.reserved, 0)

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))


def generate_reference():
    stamp = timezone.localdate().strftime("%y%m%d")
    suffix = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))
    return f"RC-{stamp}-{suffix}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        RESCHEDULED = "RESCHEDULED", "Rescheduled (make-up collection)"
        COLLECTED = "COLLECTED", "Collected"
        MISSED = "MISSED", "Missed"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"

    class Quantity(models.TextChoices):
        SMALL = "SMALL", "Small (1-2 bags or boxes)"
        MEDIUM = "MEDIUM", "Medium (3-5 bags or boxes)"
        LARGE = "LARGE", "Large / bulky items"

    ACTIVE_STATUSES = (Status.CONFIRMED, Status.RESCHEDULED)

    reference = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")

    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)
    address_line = models.CharField(max_length=255)
    suburb = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=4)

    waste_type = models.ForeignKey(WasteType, on_delete=models.PROTECT, related_name="bookings")
    quantity = models.CharField(max_length=10, choices=Quantity.choices, default=Quantity.SMALL)
    special_instructions = models.TextField(blank=True)

    provider = models.ForeignKey(
        Provider, on_delete=models.PROTECT, null=True, blank=True, related_name="bookings"
    )
    slot = models.ForeignKey(
        CollectionSlot, on_delete=models.PROTECT, null=True, blank=True, related_name="bookings"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    rejection_reason = models.CharField(max_length=255, blank=True)
    missed_count = models.PositiveSmallIntegerField(default=0)
    reminder_sent_for = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_reference()
            while Booking.objects.filter(reference=self.reference).exists():
                self.reference = generate_reference()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def change_deadline(self):
        if not self.slot:
            return None
        return self.slot.starts_at - timedelta(hours=settings.RECYCLING["CHANGE_CUTOFF_HOURS"])

    @property
    def can_change(self):
        deadline = self.change_deadline
        return self.is_active and deadline is not None and timezone.now() < deadline


class Payment(models.Model):
    class Status(models.TextChoices):
        AUTHORISED = "AUTHORISED", "Authorised"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="payment")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="AUD")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AUTHORISED)
    transaction_id = models.CharField(max_length=64)
    receipt_number = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.receipt_number


class Notification(models.Model):
    class Kind(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", "Booking confirmation"
        RESCHEDULED = "RESCHEDULED", "Booking rescheduled"
        CANCELLATION = "CANCELLATION", "Booking cancelled"
        REMINDER = "REMINDER", "Collection reminder"
        MISSED_COLLECTION = "MISSED_COLLECTION", "Missed collection"
        COLLECTED = "COLLECTED", "Collection completed"
        REJECTION = "REJECTION", "Booking rejected"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    delivered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class BookingEvent(models.Model):
    """Audit trail of status changes so no confirmation is ever lost (BRD QoS)."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12, choices=Booking.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
