from django.conf import settings
from django.db import models


class PaymentStatus(models.TextChoices):
    UNPAID = "UNPAID", "Not paid"
    DEPOSIT_PAID = "DEPOSIT", "Deposit paid"
    PAID = "PAID", "Paid in full"
    REFUNDED = "REFUNDED", "Refunded"


class SolarRequest(models.Model):
    """A solar installation request: a free site assessment booking plus the quote estimate."""

    PaymentStatus = PaymentStatus

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Assessment booked"
        ASSESSED = "ASSESSED", "Site assessed"
        COMPLETED = "COMPLETED", "Installed"
        CANCELLED = "CANCELLED", "Cancelled"

    # Requests still in progress (count towards the dashboard; the customer can still cancel).
    ACTIVE_STATUSES = (Status.CONFIRMED, Status.ASSESSED)

    # What staff can move a request to from each status.
    STAFF_TRANSITIONS = {
        Status.CONFIRMED: (Status.ASSESSED, Status.CANCELLED),
        Status.ASSESSED: (Status.COMPLETED, Status.CANCELLED),
        Status.COMPLETED: (),
        Status.CANCELLED: (),
    }

    reference = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solar_requests")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED, db_index=True)

    # Contact
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)

    # Installation address
    address_line = models.CharField(max_length=255)
    suburb = models.CharField(max_length=100)
    postcode = models.CharField(max_length=4)
    installer = models.CharField(max_length=100)

    # Property and energy use
    property_type = models.CharField(max_length=20)
    storeys = models.CharField(max_length=20)
    roof_type = models.CharField(max_length=20)
    quarterly_usage_kwh = models.PositiveIntegerField()

    # System
    system_size = models.CharField(max_length=20)
    add_ons = models.JSONField(default=list, blank=True)
    total_price = models.DecimalField(max_digits=9, decimal_places=2)

    # Site assessment
    assessment_date = models.DateField(db_index=True)
    time_slot = models.CharField(max_length=4)
    notes = models.TextField(blank=True)

    # Latest note from staff (shown to the customer)
    staff_note = models.TextField(blank=True)

    # Payment (demo card payments: see services.take_payment)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID,
                                      db_index=True)
    amount_paid = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assessment_date", "time_slot"]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def allowed_transitions(self):
        return list(self.STAFF_TRANSITIONS.get(self.status, ()))


class SolarRequestEvent(models.Model):
    """Audit trail: every status change on a solar request, shown as a timeline."""

    request = models.ForeignKey(SolarRequest, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12, choices=SolarRequest.Status.choices)
    note = models.TextField(blank=True)
    actor = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.request.reference}: {self.status}"


class SolarPayment(models.Model):
    """One payment or refund on a solar request. Only the card brand and last 4 digits are kept."""

    class Kind(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        FULL = "FULL", "Full payment"
        BALANCE = "BALANCE", "Balance payment"
        REFUND = "REFUND", "Refund"

    request = models.ForeignKey(SolarRequest, on_delete=models.CASCADE, related_name="payments")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    card_brand = models.CharField(max_length=20)
    card_last4 = models.CharField(max_length=4)
    receipt_number = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.receipt_number}: {self.get_kind_display()} ${self.amount}"
