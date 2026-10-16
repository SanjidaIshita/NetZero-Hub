from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import SolarRequest
from .services import availability


class SolarApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("priya", "priya@example.com", "S3cure-pass-123")
        self.other = get_user_model().objects.create_user("sam", "sam@example.com", "S3cure-pass-123")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def payload(self, **overrides):
        slot = availability()[0]["id"]
        data = {
            "customer_name": "Priya Shah",
            "customer_email": "priya@example.com",
            "customer_phone": "0400 123 456",
            "address_line": "17B Blacket St",
            "suburb": "North Wollongong",
            "postcode": "2500",
            "property_type": "house",
            "storeys": "double",
            "roof_type": "terracotta",
            "quarterly_usage_kwh": 1800,
            "system_size": "5kw",
            "add_ons": ["battery", "monitoring"],
            "slot_id": slot,
            "notes": "Dog in the backyard",
        }
        data.update(overrides)
        return data

    # --- public reference data -------------------------------------------------------------
    def test_options_and_postcode_are_public(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/v1/solar/options/").status_code, 200)
        res = anon.get("/api/v1/solar/postcode/", {"postcode": "2500"})
        self.assertTrue(res.data["eligible"])
        self.assertIn("NORTH WOLLONGONG", res.data["suburbs"])
        self.assertFalse(anon.get("/api/v1/solar/postcode/", {"postcode": "0800"}).data["eligible"])

    def test_recommendation_from_usage(self):
        res = self.client.get("/api/v1/solar/recommend/", {"quarterly_usage_kwh": 1800})
        self.assertEqual(res.data["recommended"]["id"], "5kw")

    def test_availability_needs_login(self):
        self.assertEqual(APIClient().get("/api/v1/solar/availability/").status_code, 401)
        slots = self.client.get("/api/v1/solar/availability/").data["slots"]
        self.assertTrue(slots)
        self.assertEqual(set(slots[0]), {"id", "date", "start_time", "end_time", "remaining"})

    # --- creating a request ---------------------------------------------------------------
    def test_create_request_prices_and_confirms(self):
        res = self.client.post("/api/v1/solar/requests/", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["service_id"], "ORG-001")
        self.assertEqual(res.data["status"], "CONFIRMED")
        self.assertTrue(res.data["reference"].startswith("ORG-001-"))
        self.assertEqual(res.data["system"]["name"], "5kW system")  # the size chosen is the size stored
        # 5490 system + 350 terracotta + 300 double storey + 8990 battery + 299 monitoring
        self.assertEqual(float(res.data["total_price"]), 15429.0)
        self.assertEqual(res.data["installer"], "Illawarra Solar Installs")

    def test_usage_must_be_positive(self):
        res = self.client.post("/api/v1/solar/requests/", self.payload(quarterly_usage_kwh=0), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], "precondition_failed")

    def test_postcode_outside_service_area(self):
        res = self.client.post("/api/v1/solar/requests/", self.payload(postcode="0800"), format="json")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], "not_eligible")

    def test_invalid_choices_are_rejected(self):
        res = self.client.post("/api/v1/solar/requests/", self.payload(system_size="99kw"), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("system_size", res.data)

    def test_full_slot_is_refused(self):
        slot = availability()[0]
        for _ in range(slot["remaining"]):
            self.assertEqual(self.client.post("/api/v1/solar/requests/", self.payload(slot_id=slot["id"]),
                                              format="json").status_code, 201)
        res = self.client.post("/api/v1/solar/requests/", self.payload(slot_id=slot["id"]), format="json")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data["code"], "slot_unavailable")

    # --- viewing and cancelling -----------------------------------------------------------
    def test_list_detail_cancel_and_privacy(self):
        ref = self.client.post("/api/v1/solar/requests/", self.payload(), format="json").data["reference"]
        self.assertEqual(len(self.client.get("/api/v1/solar/requests/").data), 1)

        other = APIClient()
        other.force_authenticate(self.other)
        self.assertEqual(other.get(f"/api/v1/solar/requests/{ref}/").status_code, 404)

        res = self.client.post(f"/api/v1/solar/requests/{ref}/cancel/")
        self.assertEqual(res.data["status"], "CANCELLED")
        again = self.client.post(f"/api/v1/solar/requests/{ref}/cancel/")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.client.get("/api/v1/solar/requests/", {"scope": "upcoming"}).data, [])

    def test_dashboard_counts(self):
        self.client.post("/api/v1/solar/requests/", self.payload(), format="json")
        res = self.client.get("/api/v1/dashboard/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["solar_count"], 1)
        self.assertEqual(res.data["recycling_count"], 0)
        self.assertEqual(SolarRequest.objects.count(), 1)
