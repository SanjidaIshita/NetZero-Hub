from django.conf import settings
from django.db import models


class SolarRequest(models.Model):
    """A solar installation request: a free site assessment booking plus the quote estimate."""

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    ACTIVE_STATUSES = (Status.CONFIRMED,)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assessment_date", "time_slot"]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
