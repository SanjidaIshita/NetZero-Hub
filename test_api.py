from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from recycling.models import Booking

from .helpers import PROVIDER_KEY, SeededMixin

INTEGRATION_KEY = "integration-test-key"


class ApiTests(SeededMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def login(self):
        res = self.client.post("/api/v1/auth/login/", {"username": "alex", "password": "S3cure-pass-123"})
        self.assertEqual(res.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")

    def payload(self, **overrides):
        data = self.details(waste_type="mixed-recycling", slot_id=self.slot().id)
        data.update(overrides)
        return data

    def test_register_returns_token(self):
        res = self.client.post(
            "/api/v1/auth/register/",
            {"username": "sam", "email": "sam@example.com", "password": "An0ther-good-pass"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("token", res.data)

    def test_booking_requires_login(self):
        res = self.client.post("/api/v1/bookings/", self.payload(), format="json")
        self.assertEqual(res.status_code, 401)

    def test_availability_and_booking_flow(self):
        self.login()
        res = self.client.get("/api/v1/availability/", {"postcode": "2500", "waste_type": "mixed-recycling"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["slots"])
        slot_id = res.data["slots"][0]["id"]

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post("/api/v1/bookings/", self.payload(slot_id=slot_id), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["booking_status"], "CONFIRMED")
        reference = res.data["booking_reference"]

        output = self.client.get(f"/api/v1/bookings/{reference}/output/").data
        for key in (
            "booking_reference",
            "confirmed_collection",
            "waste_type",
            "provider_contact",
            "booking_status",
            "notification",
        ):
            self.assertIn(key, output)
        self.assertEqual(output["notification"]["kind"], "CONFIRMATION")
        self.assertEqual(output["provider_contact"]["name"], self.provider.name)

        res = self.client.get("/api/v1/bookings/", {"scope": "upcoming"})
        self.assertEqual([b["booking_reference"] for b in res.data], [reference])

    def test_outside_area_returns_422_with_reference(self):
        self.login()
        res = self.client.post("/api/v1/bookings/", self.payload(postcode="3000"), format="json")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], "not_eligible")
        self.assertTrue(Booking.objects.filter(reference=res.data["booking_reference"]).exists())

    def test_quote(self):
        self.login()
        res = self.client.post("/api/v1/bookings/quote/", {"waste_type": "e-waste", "quantity": "SMALL"})
        self.assertEqual(res.data["fee"], "25.00")
        self.assertTrue(res.data["chargeable"])

    def test_residents_cannot_see_each_others_bookings(self):
        self.login()
        reference = self.client.post("/api/v1/bookings/", self.payload(), format="json").data["booking_reference"]
        other = APIClient()
        other.post(
            "/api/v1/auth/register/",
            {"username": "sam", "email": "sam@example.com", "password": "An0ther-good-pass"},
        )
        token = other.post("/api/v1/auth/login/", {"username": "sam", "password": "An0ther-good-pass"}).data["token"]
        other.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(other.get(f"/api/v1/bookings/{reference}/").status_code, 404)

    def test_provider_callback_requires_key(self):
        self.login()
        reference = self.client.post("/api/v1/bookings/", self.payload(), format="json").data["booking_reference"]
        provider = APIClient()
        res = provider.post(f"/api/v1/provider/collections/{reference}/missed/", {"reason": "Blocked access"})
        self.assertIn(res.status_code, (401, 403))

        provider.credentials(HTTP_X_PROVIDER_KEY=PROVIDER_KEY)
        res = provider.post(f"/api/v1/provider/collections/{reference}/missed/", {"reason": "Blocked access"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["booking_status"], "RESCHEDULED")

    def test_integration_api_exposes_outputs(self):
        with self.settings(RECYCLING={**settings.RECYCLING, "INTEGRATION_API_KEYS": [INTEGRATION_KEY]}):
            self._check_integration_api()

    def _check_integration_api(self):
        self.login()
        reference = self.client.post("/api/v1/bookings/", self.payload(), format="json").data["booking_reference"]

        anon = APIClient()
        self.assertIn(anon.get("/api/v1/integration/bookings/").status_code, (401, 403))

        anon.credentials(HTTP_X_API_KEY=INTEGRATION_KEY)
        res = anon.get("/api/v1/integration/bookings/", {"status": "confirmed"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]["booking_reference"], reference)
        self.assertEqual(res.data[0]["service_id"], "WMS-002")

        res = anon.get(f"/api/v1/integration/bookings/{reference}/")
        self.assertEqual(res.data["booking_status"], "CONFIRMED")

    def test_schema_and_health(self):
        self.assertEqual(self.client.get("/api/v1/health/").status_code, 200)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
