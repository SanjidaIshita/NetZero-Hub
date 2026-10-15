"""Service layer following the SoaML composition in BRD Part C.5.

- eligibility:   EligibilityChecker (login + service area + supported waste type)
- provider:      IProviderScheduling adapter (service area, slots, reserve/release, make-up)
- payment:       IPayment adapter (quote, authorise, receipt, refund)
- notifications: INotification adapter (confirmation, reminder, missed-collection notices)
- webhooks:      pushes WMS-002 service outputs to a downstream service, if configured
- orchestrator:  BookingOrchestrator composing the above into the resident-facing operations
"""
