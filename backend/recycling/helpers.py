import io
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from recycling.models import CollectionSlot, Provider, WasteType

PROVIDER_KEY = "test-provider-key"


class SeededMixin:
    """Seeds the same reference data as production, plus a resident."""

    def setUp(self):
        super().setUp()
        with mock.patch.dict(os.environ, {"PROVIDER_API_KEY": PROVIDER_KEY}):
            call_command("seed_data", days=20, stdout=io.StringIO())
        self.provider = Provider.objects.get()
        self.user = get_user_model().objects.create_user("alex", "alex@example.com", "S3cure-pass-123")
        self.mixed = WasteType.objects.get(code="mixed-recycling")
        self.ewaste = WasteType.objects.get(code="e-waste")
        self.mattress = WasteType.objects.get(code="mattresses")

    def slot(self, days_ahead=3, index=0):
        day = timezone.localdate() + timedelta(days=days_ahead)
        if day.weekday() == 6:
            day += timedelta(days=1)
        return CollectionSlot.objects.filter(provider=self.provider, date=day).order_by("start_time")[index]

    def details(self, **overrides):
        data = {
            "customer_name": "Alex Resident",
            "customer_email": "alex@example.com",
            "customer_phone": "0400 123 456",
            "address_line": "12 Crown Street",
            "suburb": "",
            "postcode": "2500",
            "waste_type": self.mixed,
            "quantity": "SMALL",
            "special_instructions": "Next to the letterbox",
        }
        data.update(overrides)
        return data

    def make_slot_tomorrow_morning(self):
        """A slot starting in two hours: always inside the change cut-off window."""
        start = (timezone.localtime() + timedelta(hours=2)).replace(second=0, microsecond=0)
        return CollectionSlot.objects.create(
            provider=self.provider,
            date=start.date(),
            start_time=start.time(),
            end_time=(start + timedelta(minutes=30)).time(),
            capacity=5,
        )
