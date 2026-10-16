"""Seed reference data: provider, service areas, waste types, collection timetable and demo users.

Idempotent - safe to run on every container start. `--slots-only` just rolls the provider
timetable forward, which the scheduler container does hourly.
"""

import os
from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from recycling.models import CollectionSlot, Provider, ServiceArea, WasteType

SERVICE_AREAS = [
    ("2500", "Wollongong"),
    ("2502", "Warrawong"),
    ("2505", "Port Kembla"),
    ("2506", "Berkeley"),
    ("2508", "Helensburgh"),
    ("2515", "Thirroul"),
    ("2516", "Bulli"),
    ("2517", "Woonona"),
    ("2518", "Corrimal"),
    ("2519", "Fairy Meadow"),
    ("2525", "Figtree"),
    ("2526", "Unanderra"),
    ("2530", "Dapto"),
]

# (code, name, description, accepted items, is_special, fee, supported by provider)
WASTE_TYPES = [
    (
        "mixed-recycling",
        "Mixed recycling",
        "Extra household recycling beyond your yellow-lid bin.",
        "Glass bottles and jars, plastic bottles and containers (1-5), steel and aluminium cans, milk and juice cartons.",
        False, "0.00", True,
    ),
    (
        "paper-cardboard",
        "Paper and cardboard",
        "Flattened boxes and bundled paper, e.g. after moving house.",
        "Flattened cardboard boxes, newspapers, magazines, office paper. No waxed or food-soiled cardboard.",
        False, "0.00", True,
    ),
    (
        "soft-plastics",
        "Soft plastics",
        "Scrunchable plastics collected separately for specialist recycling.",
        "Plastic bags, bread bags, cling wrap, chip packets, bubble wrap. Must be clean and dry.",
        False, "0.00", True,
    ),
    (
        "e-waste",
        "E-waste",
        "Electronic items recovered for metals and components (special collection).",
        "Computers, laptops, TVs, monitors, phones, printers, small appliances, cables.",
        True, "25.00", True,
    ),
    (
        "scrap-metal-whitegoods",
        "Scrap metal and whitegoods",
        "Large metal items and appliances (special collection).",
        "Fridges (doors removed), washing machines, dryers, ovens, metal furniture, bikes, BBQs (no gas bottles).",
        True, "45.00", True,
    ),
    (
        "mattresses",
        "Mattresses",
        "Mattress recycling (not currently offered by the provider in this area).",
        "Mattresses and bases.",
        True, "60.00", False,
    ),
]

SLOT_WINDOWS = [(time(7, 0), time(11, 0)), (time(11, 0), time(15, 0))]
SLOT_CAPACITY = 20


class Command(BaseCommand):
    help = "Seed WMS-002 reference data and roll the collection timetable forward."

    def add_arguments(self, parser):
        parser.add_argument("--slots-only", action="store_true", help="Only create upcoming slots.")
        parser.add_argument("--days", type=int, default=None, help="Days of timetable to create.")

    @transaction.atomic
    def handle(self, *args, slots_only=False, days=None, **options):
        provider = Provider.objects.order_by("pk").first()
        if not slots_only or provider is None:
            provider = self._seed_reference_data()
            self._seed_users()
        created = self._seed_slots(provider, days or settings.RECYCLING["BOOKING_WINDOW_DAYS"] + 7)
        self.stdout.write(self.style.SUCCESS(f"Seed complete ({created} new collection slots)."))

    def _seed_reference_data(self):
        provider, _ = Provider.objects.update_or_create(
            name=os.environ.get("PROVIDER_NAME", "Cleanaway Waste Management"),
            defaults={
                "phone": os.environ.get("PROVIDER_PHONE", "1300 000 000"),
                "email": os.environ.get("PROVIDER_EMAIL", "recycling@provider.example"),
                "website": os.environ.get("PROVIDER_WEBSITE", ""),
                "api_key": os.environ.get("PROVIDER_API_KEY", "dev-provider-key"),
            },
        )
        for postcode, suburb in SERVICE_AREAS:
            ServiceArea.objects.update_or_create(postcode=postcode, defaults={"suburb": suburb, "provider": provider})

        for order, (code, name, desc, items, special, fee, supported) in enumerate(WASTE_TYPES):
            waste_type, _ = WasteType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": desc,
                    "accepted_items": items,
                    "is_special": special,
                    "base_fee": Decimal(fee),
                    "sort_order": order,
                },
            )
            if supported:
                provider.waste_types.add(waste_type)
            else:
                provider.waste_types.remove(waste_type)
        return provider

    def _seed_users(self):
        User = get_user_model()
        demo_password = os.environ.get("DEMO_RESIDENT_PASSWORD")
        if demo_password and not User.objects.filter(username="resident").exists():
            User.objects.create_user(
                "resident", "resident@example.com", demo_password, first_name="Alex", last_name="Resident"
            )
            self.stdout.write("Created demo resident user 'resident'.")
        staff_password = os.environ.get("DEMO_STAFF_PASSWORD")
        if staff_password and not User.objects.filter(username="provider_admin").exists():
            User.objects.create_superuser("provider_admin", "admin@example.com", staff_password)
            self.stdout.write("Created staff user 'provider_admin'.")

    def _seed_slots(self, provider, days):
        today = timezone.localdate()
        created = 0
        for offset in range(days):
            day = today + timedelta(days=offset)
            if day.weekday() == 6:  # no Sunday collections
                continue
            for start, end in SLOT_WINDOWS:
                _, was_created = CollectionSlot.objects.get_or_create(
                    provider=provider,
                    date=day,
                    start_time=start,
                    defaults={"end_time": end, "capacity": SLOT_CAPACITY},
                )
                created += was_created
        return created
