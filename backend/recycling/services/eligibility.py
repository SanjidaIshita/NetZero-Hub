"""EligibilityChecker: WMS-002 pre-conditions that can be checked before booking."""

from . import provider as provider_api
from .exceptions import NotEligible


def check(user, postcode, waste_type):
    """Return the ServiceArea serving `postcode`, or raise NotEligible."""
    if user is None or not user.is_authenticated:
        raise NotEligible("You must be logged in to book a recycling collection.", reason="not_logged_in")

    area = provider_api.check_service_area(postcode)
    if area is None:
        raise NotEligible(
            f"Postcode {postcode} is outside the recycling collection service area.",
            reason="outside_service_area",
        )

    if not waste_type.active or not area.provider.waste_types.filter(pk=waste_type.pk).exists():
        raise NotEligible(
            f"{waste_type.name} is not collected by {area.provider.name} in your area.",
            reason="waste_type_not_supported",
        )
    return area
