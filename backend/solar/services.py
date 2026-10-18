"""Business rules for the Solar Panel Installation service (ORG-001)."""
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .catalogue import ADD_ONS, ROOF_TYPES, SERVICE_ID, STOREYS, SYSTEM_SIZES, TIME_SLOTS, by_id
from .models import SolarPayment, SolarRequest, SolarRequestEvent


def today():
    return timezone.localdate()


def available_dates(days_ahead=21):
    """Site assessments run Monday to Saturday, starting tomorrow."""
    start = today() + timedelta(days=1)
    days = (start + timedelta(days=i) for i in range(days_ahead))
    return [d for d in days if d.weekday() != 6]


def slot_capacity(day, slot):
    return slot["capacity"] if day.weekday() < 5 else slot["capacity"] // 2


def booked_count(day, slot_id):
    return SolarRequest.objects.filter(
        assessment_date=day, time_slot=slot_id, status__in=SolarRequest.ACTIVE_STATUSES
    ).count()


def slot_id_for(day, slot_id):
    return f"{day.isoformat()}|{slot_id}"


def availability():
    """Slots in the same shape the recycling SlotPicker uses: id, date, start_time, end_time, remaining."""
    slots = []
    for day in available_dates():
        for slot in TIME_SLOTS:
            remaining = slot_capacity(day, slot) - booked_count(day, slot["id"])
            if remaining > 0:
                slots.append({
                    "id": slot_id_for(day, slot["id"]),
                    "date": day.isoformat(),
                    "start_time": slot["start"],
                    "end_time": slot["end"],
                    "remaining": remaining,
                })
    return slots


def recommend_size(quarterly_usage_kwh):
    """About 4 peak sun hours a day in NSW, so size the system to the daily use."""
    if not quarterly_usage_kwh or quarterly_usage_kwh <= 0:
        return None
    daily = quarterly_usage_kwh / 91
    return next((s for s in SYSTEM_SIZES if daily <= s["dailyKwh"]), SYSTEM_SIZES[-1])


def price_breakdown(system_size, roof_type, storeys, add_ons):
    system = by_id(SYSTEM_SIZES, system_size)
    roof = by_id(ROOF_TYPES, roof_type)
    storey = by_id(STOREYS, storeys)
    lines = [{"item": system["name"], "amount": system["price"]}]
    if roof["surcharge"]:
        lines.append({"item": f"{roof['name']} roof mounting", "amount": roof["surcharge"]})
    if storey["surcharge"]:
        lines.append({"item": f"{storey['name']} access", "amount": storey["surcharge"]})
    for add_on_id in add_ons:
        add_on = by_id(ADD_ONS, add_on_id)
        lines.append({"item": add_on["name"], "amount": add_on["price"]})
    return lines


def new_reference():
    return f"{SERVICE_ID}-{timezone.localtime():%y%m%d}-{uuid.uuid4().hex[:5].upper()}"


# --------------------------------------------------------------------------------------------
# Payments (demo only: no real card is charged; only the card brand and last 4 digits are stored)
# --------------------------------------------------------------------------------------------
DEPOSIT_RATE = Decimal("0.10")
DECLINED_TEST_CARD = "4000000000000002"  # use this number to try a declined payment


def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def deposit_amount(obj):
    """10% of the quote, in whole dollars."""
    return (Decimal(obj.total_price) * DEPOSIT_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def balance_due(obj):
    if obj.status == SolarRequest.Status.CANCELLED:
        return Decimal("0.00")
    return money(Decimal(obj.total_price) - Decimal(obj.amount_paid))


def payment_options(obj):
    """What the customer can pay right now."""
    if obj.status == SolarRequest.Status.CANCELLED or balance_due(obj) <= 0:
        return []
    if Decimal(obj.amount_paid) == 0:
        return [
            {"id": "deposit", "label": "Pay 10% deposit", "amount": money(deposit_amount(obj)),
             "description": "Secures your installation. Pay the rest after the site assessment."},
            {"id": "full", "label": "Pay in full", "amount": balance_due(obj),
             "description": "Pay the whole estimate now and you're all done."},
        ]
    return [{"id": "balance", "label": "Pay remaining balance", "amount": balance_due(obj),
             "description": "Pay what's left of your quote."}]


def luhn_ok(number):
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def card_brand(number):
    if number.startswith("4"):
        return "Visa"
    if number[:2] in {"34", "37"}:
        return "American Express"
    if 51 <= int(number[:2]) <= 55 or 2221 <= int(number[:4]) <= 2720:
        return "Mastercard"
    return None


def card_errors(number, expiry, cvc):
    """Field errors for a card, or {} if it looks valid."""
    errors = {}
    brand = card_brand(number) if number.isdigit() and len(number) >= 4 else None
    if not (number.isdigit() and 13 <= len(number) <= 19 and luhn_ok(number)):
        errors["card_number"] = ["Enter a valid card number."]
    elif not brand:
        errors["card_number"] = ["We accept Visa, Mastercard and American Express."]
    try:
        month, year = expiry.split("/")
        month, year = int(month), 2000 + int(year)
        if not 1 <= month <= 12:
            raise ValueError
        first_of_next = date(year + month // 12, month % 12 + 1, 1)
        if first_of_next <= today():
            errors["expiry"] = ["This card has expired."]
    except ValueError:
        errors["expiry"] = ["Enter the expiry as MM/YY."]
    cvc_len = 4 if brand == "American Express" else 3
    if not (cvc.isdigit() and len(cvc) == cvc_len):
        errors["cvc"] = [f"Enter the {cvc_len}-digit security code."]
    return errors


def new_receipt():
    return f"RCPT-{timezone.localtime():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def update_payment_status(obj):
    paid = Decimal(obj.amount_paid)
    if paid <= 0:
        obj.payment_status = (SolarRequest.PaymentStatus.REFUNDED if obj.payments.filter(kind="REFUND").exists()
                              else SolarRequest.PaymentStatus.UNPAID)
    elif paid >= Decimal(obj.total_price):
        obj.payment_status = SolarRequest.PaymentStatus.PAID
    else:
        obj.payment_status = SolarRequest.PaymentStatus.DEPOSIT_PAID


def record_payment(obj, kind, amount, brand, last4, actor):
    """Save a payment (call inside a transaction with obj locked) and add it to the timeline."""
    payment = SolarPayment.objects.create(request=obj, kind=kind, amount=amount, card_brand=brand,
                                          card_last4=last4, receipt_number=new_receipt())
    obj.amount_paid = money(Decimal(obj.amount_paid) + amount)
    update_payment_status(obj)
    obj.save(update_fields=["amount_paid", "payment_status", "updated_at"])
    activity = {"DEPOSIT": SolarRequestEvent.Activity.PAY_DEPOSIT, "FULL": SolarRequestEvent.Activity.PAY_FULL,
                "BALANCE": SolarRequestEvent.Activity.PAY_BALANCE}[kind]
    SolarRequestEvent.objects.create(
        request=obj, activity=activity, status=obj.status, actor=actor,
        note=f"{payment.get_kind_display()} of ${amount:,.2f} paid ({brand} ending {last4}). "
             f"Receipt {payment.receipt_number}.",
    )
    return payment


def refund_all(obj):
    """Refund everything paid on a request (call after cancelling it, inside the same transaction).
    Saves the request and adds an "Issue refund" event. Returns the amount refunded."""
    paid = money(obj.amount_paid)
    if paid <= 0:
        return Decimal("0.00")
    last = obj.payments.exclude(kind="REFUND").last()
    SolarPayment.objects.create(request=obj, kind="REFUND", amount=paid, card_brand=last.card_brand,
                                card_last4=last.card_last4, receipt_number=new_receipt())
    obj.amount_paid = Decimal("0.00")
    obj.payment_status = SolarRequest.PaymentStatus.REFUNDED
    obj.save(update_fields=["amount_paid", "payment_status", "updated_at"])
    SolarRequestEvent.objects.create(
        request=obj, activity=SolarRequestEvent.Activity.REFUND, status=obj.status, actor="NetZero Hub",
        note=f"Refund of ${paid:,.2f} issued to {last.card_brand} ending {last.card_last4}.",
    )
    return paid
