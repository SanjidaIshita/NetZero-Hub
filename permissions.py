import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission

from .models import Provider


def _matches(supplied, expected):
    return bool(supplied) and bool(expected) and hmac.compare_digest(supplied, expected)


class HasIntegrationKey(BasePermission):
    """Other services read WMS-002 outputs with an X-API-Key header (or as a staff user)."""

    message = "A valid X-API-Key header is required."

    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        supplied = request.headers.get("X-API-Key", "")
        return any(_matches(supplied, key) for key in settings.RECYCLING["INTEGRATION_API_KEYS"])


class IsProviderOrStaff(BasePermission):
    """ICollectionStatus callback: the provider authenticates with X-Provider-Key.

    On success the matching provider is stored on request.provider (None for staff users).
    """

    message = "A valid X-Provider-Key header is required."

    def has_permission(self, request, view):
        supplied = request.headers.get("X-Provider-Key", "")
        if supplied:
            for provider in Provider.objects.all():
                if _matches(supplied, provider.api_key):
                    request.provider = provider
                    return True
        if request.user and request.user.is_staff:
            request.provider = None
            return True
        return False
