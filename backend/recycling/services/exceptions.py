class ServiceError(Exception):
    """Business-rule failure, rendered by the API as {"code", "detail", ...extra}."""

    status_code = 400
    code = "service_error"

    def __init__(self, message, **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra


class NotEligible(ServiceError):
    status_code = 422
    code = "not_eligible"


class SlotUnavailable(ServiceError):
    status_code = 409
    code = "slot_unavailable"


class FeeNotAccepted(ServiceError):
    status_code = 400
    code = "fee_acceptance_required"


class PaymentFailed(ServiceError):
    status_code = 402
    code = "payment_failed"


class ChangeNotAllowed(ServiceError):
    status_code = 409
    code = "change_not_allowed"
