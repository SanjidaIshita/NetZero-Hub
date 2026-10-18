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


class SolarAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user("priya", "priya@example.com", "S3cure-pass-123", first_name="Priya")
        self.staff = User.objects.create_user("installer", "staff@example.com", "S3cure-pass-123", is_staff=True,
                                              first_name="Sam", last_name="Installer")
        self.client = APIClient()
        self.client.force_authenticate(self.customer)
        self.ref = self.client.post("/api/v1/solar/requests/", SolarApiTests.payload(self), format="json").data["reference"]
        self.admin = APIClient()
        self.admin.force_authenticate(self.staff)

    def test_customers_cannot_use_admin_api(self):
        for url in ("/api/v1/solar/admin/summary/", "/api/v1/solar/admin/requests/"):
            self.assertEqual(self.client.get(url).status_code, 403)
        res = self.client.post(f"/api/v1/solar/admin/requests/{self.ref}/status/", {"status": "ASSESSED"})
        self.assertEqual(res.status_code, 403)

    def test_summary_and_list(self):
        summary = self.admin.get("/api/v1/solar/admin/summary/").data
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["by_status"]["CONFIRMED"], 1)
        self.assertEqual(float(summary["pipeline_value"]), 15429.0)
        rows = self.admin.get("/api/v1/solar/admin/requests/", {"q": "priya"}).data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["customer_account"]["username"], "priya")
        self.assertEqual([t["status"] for t in rows[0]["allowed_transitions"]], ["ASSESSED", "CANCELLED"])
        self.assertEqual(self.admin.get("/api/v1/solar/admin/requests/", {"status": "COMPLETED"}).data, [])

    def test_workflow_and_customer_timeline(self):
        url = f"/api/v1/solar/admin/requests/{self.ref}/status/"
        # Can't jump straight to installed
        self.assertEqual(self.admin.post(url, {"status": "COMPLETED"}).status_code, 409)
        res = self.admin.post(url, {"status": "ASSESSED", "note": "Roof suits 13 panels facing north."})
        self.assertEqual(res.data["status"], "ASSESSED")
        res = self.admin.post(url, {"status": "COMPLETED", "note": "System installed and switched on."})
        self.assertEqual(res.data["status"], "COMPLETED")
        self.assertEqual(res.data["allowed_transitions"], [])
        # Finished requests can't change again
        self.assertEqual(self.admin.post(url, {"status": "CANCELLED"}).status_code, 409)

        mine = self.client.get(f"/api/v1/solar/requests/{self.ref}/").data
        self.assertEqual([e["status"] for e in mine["history"]], ["CONFIRMED", "ASSESSED", "COMPLETED"])
        self.assertEqual(mine["history"][1]["actor"], "Sam Installer")
        self.assertEqual(mine["staff_note"], "System installed and switched on.")
        self.assertFalse(mine["can_cancel"])
        self.assertEqual(self.admin.get("/api/v1/solar/admin/summary/").data["by_status"]["COMPLETED"], 1)


class SolarPaymentTests(TestCase):
    """Demo card payments: 10% deposit or full amount, then the balance; refunds on cancellation."""

    CARD = {"cardholder_name": "Priya Shah", "card_number": "4242 4242 4242 4242", "expiry": "12/30", "cvc": "123"}

    def setUp(self):
        self.user = get_user_model().objects.create_user("priya", "priya@example.com", "S3cure-pass-123")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.ref = self.client.post("/api/v1/solar/requests/", SolarApiTests.payload(self), format="json").data["reference"]
        self.url = f"/api/v1/solar/requests/{self.ref}/pay/"

    def pay(self, option, **card):
        return self.client.post(self.url, {"option": option, **self.CARD, **card}, format="json")

    def test_new_request_is_unpaid_with_two_options(self):
        p = self.client.get(f"/api/v1/solar/requests/{self.ref}/").data["payment"]
        self.assertEqual(p["status"], "UNPAID")
        self.assertEqual(p["balance_due"], "15429.00")
        self.assertEqual([(o["id"], o["amount"]) for o in p["options"]], [("deposit", "1543.00"), ("full", "15429.00")])

    def test_deposit_then_balance(self):
        res = self.pay("deposit")
        self.assertEqual(res.status_code, 200, res.data)
        p = res.data["payment"]
        self.assertEqual((p["status"], p["amount_paid"], p["balance_due"]), ("DEPOSIT", "1543.00", "13886.00"))
        self.assertEqual([o["id"] for o in p["options"]], ["balance"])
        self.assertEqual(p["receipts"][0]["card_last4"], "4242")
        self.assertEqual(p["receipts"][0]["card_brand"], "Visa")
        self.assertIn("Deposit of $1,543.00 paid", res.data["history"][-1]["note"])
        # Can't pay the deposit twice
        self.assertEqual(self.pay("deposit").status_code, 409)

        p = self.pay("balance").data["payment"]
        self.assertEqual((p["status"], p["balance_due"], p["options"]), ("PAID", "0.00", []))
        self.assertEqual(self.pay("balance").status_code, 409)

    def test_pay_in_full(self):
        p = self.pay("full", card_number="5555 5555 5555 4444").data["payment"]
        self.assertEqual((p["status"], p["amount_paid"]), ("PAID", "15429.00"))
        self.assertEqual(p["receipts"][0]["card_brand"], "Mastercard")

    def test_card_checks(self):
        self.assertIn("card_number", self.pay("full", card_number="4242 4242 4242 4241").data)
        self.assertIn("expiry", self.pay("full", expiry="01/20").data)
        self.assertIn("expiry", self.pay("full", expiry="13/30").data)
        self.assertIn("cvc", self.pay("full", cvc="12").data)
        declined = self.pay("full", card_number="4000 0000 0000 0002")
        self.assertEqual(declined.status_code, 402)
        self.assertEqual(declined.data["code"], "payment_declined")
        self.assertEqual(SolarRequest.objects.get().payment_status, "UNPAID")

    def test_card_details_are_not_stored(self):
        self.pay("full")
        payment = SolarRequest.objects.get().payments.get()
        stored = " ".join(str(getattr(payment, f.attname)) for f in payment._meta.fields)
        self.assertNotIn("4242424242424242", stored)
        self.assertNotIn("123", stored.replace(payment.receipt_number, ""))

    def test_cancel_refunds_payment(self):
        self.pay("deposit")
        res = self.client.post(f"/api/v1/solar/requests/{self.ref}/cancel/")
        p = res.data["payment"]
        self.assertEqual((p["status"], p["amount_paid"], p["options"]), ("REFUNDED", "0.00", []))
        self.assertEqual(p["receipts"][-1]["kind"], "REFUND")
        self.assertIn("Refund of $1,543.00", res.data["history"][-1]["note"])
        self.assertEqual(self.pay("balance").status_code, 409)

    def test_staff_cancel_refunds_and_summary(self):
        staff = get_user_model().objects.create_user("installer", "s@example.com", "S3cure-pass-123", is_staff=True)
        admin = APIClient()
        admin.force_authenticate(staff)
        self.pay("full")
        self.assertEqual(float(admin.get("/api/v1/solar/admin/summary/").data["payments_received"]), 15429.0)
        res = admin.post(f"/api/v1/solar/admin/requests/{self.ref}/status/", {"status": "CANCELLED", "note": "Roof unsuitable."})
        self.assertEqual(res.data["payment"]["status"], "REFUNDED")
        self.assertEqual(float(admin.get("/api/v1/solar/admin/summary/").data["payments_received"]), 0.0)

    def test_other_users_cannot_pay(self):
        other = APIClient()
        other.force_authenticate(get_user_model().objects.create_user("sam", "sam@example.com", "S3cure-pass-123"))
        res = other.post(self.url, {"option": "full", **self.CARD}, format="json")
        self.assertEqual(res.status_code, 404)
