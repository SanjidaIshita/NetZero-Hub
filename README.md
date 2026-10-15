# Recycling Collection Scheduling microservice (WMS-002)

NetZero Hub microservice that implements **Service 2: Recycling collection scheduling (WMS-002)** from the
Waste Management BRD. Residents book, reschedule and cancel recycling collections online. The provider reports
whether each collection was completed or missed, and other services read the booking outputs through a REST API
or receive them by webhook.

| Layer    | Technology                                                      |
| -------- | --------------------------------------------------------------- |
| Frontend | React 18 + Vite, served by nginx                                |
| Backend  | Python 3.12, Django 5.1, Django REST Framework, Gunicorn        |
| Database | MySQL 8.4                                                       |
| API docs | OpenAPI 3 via drf-spectacular (Swagger UI at `/api/docs/`)      |
| Runtime  | Docker Compose: `db`, `backend`, `scheduler`, `frontend`        |

## Quick start (Docker)

```bash
cp .env.example .env        # then replace every CHANGE-ME value
docker compose up --build
```

| URL                              | What                                              |
| -------------------------------- | ------------------------------------------------- |
| http://localhost:3000            | Resident web app (React)                          |
| http://localhost:3000/api/docs/  | Interactive API documentation (Swagger)           |
| http://localhost:3000/admin/     | Django admin (staff user)                         |
| http://localhost:8000/api/v1/    | Backend API directly                              |

On first start the backend runs migrations and seeds reference data. That covers the provider, Wollongong
service-area postcodes, six waste types and about two months of collection slots. If you set
`DEMO_RESIDENT_PASSWORD` / `DEMO_STAFF_PASSWORD` in `.env`, it also creates the demo users `resident` and
`provider_admin`. The staff user can open the **Provider console** to mark collections as collected or missed.

The `scheduler` container runs every hour. It sends reminders for the next day's collections and extends the
slot timetable.

## How the BRD maps to the code

| BRD WMS-002 item | Where it's implemented |
| --- | --- |
| **Inputs**: name and contact, preferred date, waste type, estimated quantity, special instructions, authentication | `BookingCreateSerializer` plus a token-authenticated request |
| **Outputs**: booking reference, confirmed date and time, waste type info, provider contact, status, notification | `BookingOutputSerializer`, the shared output contract |
| Pre-condition: logged in | DRF `IsAuthenticated` on every booking endpoint |
| Pre-condition: valid address in the service area | `services/eligibility.py` and `ServiceArea` |
| Pre-condition: date available; waste type supported | `provider.reserve_collection` (row-locked); `Provider.waste_types` |
| Post-condition: booking created with unique reference, slot reserved, status confirmed, provider receives request | `orchestrator.create_booking` (one DB transaction) |
| Post-condition: confirmation with provider contact details | `notifications.notify(CONFIRMATION)` |
| QoS: availability in under 3 s, confirmation in under 5 s | Indexed slot query; notifications and webhooks never block the transaction |
| QoS: confirmation must not be lost | Every notice is stored (`Notification`) and every status change is audited (`BookingEvent`) |
| Delivery: reminders, view upcoming, reschedule or cancel within the permitted timeframe | `send_reminders`; `?scope=upcoming`; `CHANGE_CUTOFF_HOURS` (default 24 h) |
| Payment: standard recycling free; special or large items charged and shown before confirming | `payment.quote_fee`, `POST /bookings/quote/`, `accept_fee` is required |
| Penalty: missed collection is rescheduled automatically and the customer notified | `orchestrator.collection_missed` books the next free slot (`RESCHEDULED`) |
| Penalty: incorrect information may be rejected | Rejected requests are saved as `REJECTED` with a reason and the resident is notified |
| Part C gap: refund if a paid booking is cancelled | `cancel_booking` refunds the payment |

The service layer follows the SoaML composition in BRD Part C.5. `BookingOrchestrator` composes the
`EligibilityChecker` with the `IProviderScheduling`, `IPayment` and `INotification` adapters. The
`ICollectionStatus` callback is exposed as the provider endpoints. The tests cover the four effect scenarios:
S1 rejected, S2 standard, S3 paid special collection and S4 missed then rescheduled.

```
backend/
  config/                 Django settings (MySQL via env, SQLite fallback for tests)
  recycling/
    models.py             Provider, ServiceArea, WasteType, CollectionSlot, Booking, Payment, Notification, BookingEvent
    services/             orchestrator, eligibility, provider, payment, notifications, webhooks
    serializers.py        inputs + WMS-002 output contract
    views.py, urls.py     REST API
    management/commands/  seed_data, send_reminders, wait_for_db
    tests/                24 tests
frontend/src/
  pages/                  Login, Register, Bookings, NewBooking (3-step wizard), BookingDetail, ProviderConsole
  components/             SlotPicker, StatusBadge, Field
```

## API

All paths are under `/api/v1/`. Residents authenticate with `Authorization: Token <token>`, which they get from
`auth/login/` or `auth/register/`.

### Resident (IRecyclingBooking)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `auth/register/`, `auth/login/`, `auth/logout/`; GET `auth/me/` | Account and token |
| GET | `waste-types/?postcode=2500` | Waste types collected in an area (public) |
| GET | `service-areas/check/?postcode=2500` | Is the address serviceable, and by whom (public) |
| GET | `availability/?postcode=&waste_type=&date_from=&date_to=` | Free collection slots |
| POST | `bookings/quote/` | Fee quote: `{waste_type, quantity}` |
| POST | `bookings/` | Create and confirm a booking |
| GET | `bookings/?scope=upcoming\|past` | The resident's bookings |
| GET | `bookings/{ref}/` | Booking detail with history |
| GET | `bookings/{ref}/output/` | **WMS-002 service output** |
| POST | `bookings/{ref}/reschedule/` | `{slot_id}` |
| POST | `bookings/{ref}/cancel/` | Release the slot and refund any fee |
| GET | `bookings/{ref}/notifications/` | Notices sent for this booking |

Errors that come from business rules return `{"code", "detail", ...}`, for example `not_eligible` (422),
`slot_unavailable` (409), `fee_acceptance_required` (400, includes `fee` and `breakdown`), `payment_failed`
(402) and `change_not_allowed` (409).

### Provider callback (ICollectionStatus), `X-Provider-Key` header

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `provider/collections/?date=YYYY-MM-DD` | Run sheet of active bookings |
| POST | `provider/collections/{ref}/completed/` | Mark collected |
| POST | `provider/collections/{ref}/missed/` | `{reason}`: marks missed and books a make-up collection automatically |

### Output API for other services, `X-API-Key` header (keys in `INTEGRATION_API_KEYS`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `integration/bookings/?status=&collection_date=&postcode=&updated_since=&limit=` | Feed of service outputs |
| GET | `integration/bookings/{ref}/` | One service output |

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8000/api/v1/integration/bookings/?status=CONFIRMED&collection_date=2026-10-16"
```

Example output (`BookingOutputSerializer`):

```json
{
  "service_id": "WMS-002",
  "booking_reference": "RC-261014-JQK7VU",
  "booking_status": "CONFIRMED",
  "confirmed_collection": { "date": "2026-10-17", "start_time": "07:00", "end_time": "11:00" },
  "waste_type": { "code": "mixed-recycling", "name": "Mixed recycling", "is_special": false, "...": "..." },
  "estimated_quantity": "MEDIUM",
  "provider_contact": { "name": "Cleanaway Waste Management", "phone": "1300 000 000", "email": "recycling@provider.example", "website": "" },
  "collection_address": { "address_line": "5 Princes Hwy", "suburb": "Fairy Meadow", "postcode": "2519" },
  "special_instructions": "",
  "fee": { "amount": "0.00", "currency": "AUD", "chargeable": false, "receipt_number": null, "payment_status": null },
  "notification": { "kind": "CONFIRMATION", "recipient": "resident@example.com", "subject": "…", "delivered": true, "sent_at": "…" },
  "rejection_reason": "",
  "created_at": "…",
  "updated_at": "…"
}
```

### Push outputs (webhook)

If you set `OUTPUT_WEBHOOK_URL`, every status change POSTs this payload to that URL:

```json
{"event": "booking.confirmed", "occurred_at": "…", "data": { …service output… }}
```

Events: `booking.confirmed`, `booking.rescheduled`, `booking.cancelled`, `booking.collected`,
`booking.missed`, `booking.rejected`. If `OUTPUT_WEBHOOK_SECRET` is set, the request carries
`X-Signature: sha256=<HMAC of raw body>`.

## Local development without Docker

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate      # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt                    # mysqlclient is only needed when MYSQL_HOST is set
python manage.py migrate && python manage.py seed_data
python manage.py runserver
```

```bash
cd frontend && npm install && npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

When `MYSQL_HOST` is unset, the backend uses SQLite.

## Tests

```bash
cd backend && python manage.py test recycling
```

## Before going to production

- **Payment is simulated.** `services/payment.py` accepts any token (`tok_decline` simulates a decline) and
  never handles card data. Replace it with a real gateway such as Stripe PaymentIntents, and swap the frontend's
  demo token for that gateway's checkout widget.
- **E-mail** uses Django's console backend by default, so notices print to the backend logs. Set the `EMAIL_*`
  variables to send real mail.
- **Provider timetable.** `services/provider.py` reads the provider's slots from the local table. To integrate
  the provider's own scheduling API, replace those functions with HTTP calls. The orchestrator does not change.
- The provider name comes from the BRD. Its phone number and email address are placeholders, so set the real
  details through the `PROVIDER_*` variables.
- Serve the stack over HTTPS and set `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and
  `CORS_ALLOWED_ORIGINS` to your domain.
