"""IPayment adapter for special or large-item collections.

This is a mock gateway: it never handles card details. The frontend obtains a payment
token (here a placeholder) and the gateway authorises it. Swap `authorise_payment` and
`refund` for a real provider SDK (e.g. Stripe PaymentIntents) in production.
The token "tok_decline" simulates a declined payment.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from ..models import Booking, Payment
from .exceptions import PaymentFailed


def quote_fee(waste_type, quantity):
    """Standard residential recycling is free; special and large-item collections are charged."""
    breakdown = []
    if waste_type.is_special and waste_type.base_fee > 0:
        breakdown.append({"item": f"{waste_type.name} collection", "amount": str(waste_type.base_fee)})
    if quantity == Booking.Quantity.LARGE:
        surcharge = settings.RECYCLING["LARGE_ITEM_SURCHARGE"]
        breakdown.append({"item": "Large / bulky item surcharge", "amount": str(surcharge)})
    total = sum((Decimal(line["amount"]) for line in breakdown), Decimal("0.00"))
    return total.quantize(Decimal("0.01")), breakdown


def authorise_payment(booking, amount, payment_token):
    if not payment_token:
        raise PaymentFailed("Payment is required to confirm a special or large-item collection.")
    if payment_token == "tok_decline":
        raise PaymentFailed("The payment was declined. No booking was made.")

    return Payment.objects.create(
        booking=booking,
        amount=amount,
        currency=settings.RECYCLING["CURRENCY"],
        transaction_id=f"txn_{secrets.token_hex(12)}",
        receipt_number=f"RCPT-{booking.reference}",
    )


def refund(payment):
    if payment.status == Payment.Status.AUTHORISED:
        payment.status = Payment.Status.REFUNDED
        payment.refunded_at = timezone.now()
        payment.save(update_fields=["status", "refunded_at"])
    return payment
