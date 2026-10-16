"""Push WMS-002 service outputs to a downstream service when OUTPUT_WEBHOOK_URL is set.

Each request is a JSON POST of {"event", "occurred_at", "data": <BookingOutput>} signed with
HMAC-SHA256 over the raw body in the X-Signature header (when OUTPUT_WEBHOOK_SECRET is set).
Delivery runs on a background thread so it never slows the booking response.
"""

import hashlib
import hmac
import json
import logging
import threading
import urllib.request

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

logger = logging.getLogger(__name__)


def _deliver(url, body, headers):
    try:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            logger.info("Output webhook delivered (%s)", response.status)
    except Exception:
        logger.exception("Output webhook delivery to %s failed", url)


def publish_output(booking, event):
    url = settings.RECYCLING["OUTPUT_WEBHOOK_URL"]
    if not url:
        return
    from ..serializers import BookingOutputSerializer

    payload = {
        "event": event,
        "occurred_at": timezone.now(),
        "data": BookingOutputSerializer(booking).data,
    }
    body = json.dumps(payload, cls=DjangoJSONEncoder).encode()
    headers = {"Content-Type": "application/json", "X-Event": event}
    secret = settings.RECYCLING["OUTPUT_WEBHOOK_SECRET"]
    if secret:
        headers["X-Signature"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    threading.Thread(target=_deliver, args=(url, body, headers), daemon=True).start()
