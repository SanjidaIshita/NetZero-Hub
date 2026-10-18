from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from recycling.services.exceptions import ChangeNotAllowed, NotEligible, ServiceError, SlotUnavailable

from . import services
from .catalogue import ADD_ONS, PROPERTY_TYPES, ROOF_TYPES, STOREYS, SUBURBS, SYSTEM_SIZES, TIME_SLOTS, by_id, find_installer
from .models import SolarRequest, SolarRequestEvent
from .serializers import (
    PaymentSerializer,
    SolarAdminRequestSerializer,
    SolarRequestCreateSerializer,
    SolarRequestSerializer,
    StatusUpdateSerializer,
)


class PreconditionFailed(ServiceError):
    status_code = 400
    code = "precondition_failed"


# The process activity recorded when staff move a request to each status
STAFF_ACTIVITY = {
    SolarRequest.Status.ASSESSED: SolarRequestEvent.Activity.ASSESS,
    SolarRequest.Status.COMPLETED: SolarRequestEvent.Activity.INSTALL,
    SolarRequest.Status.CANCELLED: SolarRequestEvent.Activity.CANCEL,
}


class PaymentDeclined(ServiceError):
    status_code = 402
    code = "payment_declined"


class OptionsView(APIView):
    """Everything the solar request form can offer: system sizes, roof types, property types, storeys, add-ons."""

    permission_classes = [AllowAny]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({
            "system_sizes": SYSTEM_SIZES,
            "roof_types": ROOF_TYPES,
            "property_types": PROPERTY_TYPES,
            "storeys": STOREYS,
            "add_ons": ADD_ONS,
        })


class PostcodeCheckView(APIView):
    """Is a postcode serviced, by which installer, and which suburbs it covers. ?postcode=2500"""

    permission_classes = [AllowAny]

    @extend_schema(parameters=[OpenApiParameter("postcode", str)], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        postcode = request.query_params.get("postcode", "")
        installer = find_installer(postcode)
        return Response({
            "postcode": postcode,
            "eligible": bool(installer),
            "installer": installer,
            "suburbs": SUBURBS.get(postcode, []),
        })


class RecommendView(APIView):
    """Suggested system size for a quarterly usage. ?quarterly_usage_kwh=1800"""

    permission_classes = [AllowAny]

    @extend_schema(parameters=[OpenApiParameter("quarterly_usage_kwh", int)], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        try:
            usage = int(request.query_params.get("quarterly_usage_kwh", "0"))
        except ValueError:
            usage = 0
        size = services.recommend_size(usage)
        return Response({"quarterly_usage_kwh": usage, "daily_kwh": round(usage / 91, 1) if usage > 0 else 0,
                         "recommended": size})


class AvailabilityView(APIView):
    """Free site assessment slots for the next three weeks (Monday to Saturday)."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({"slots": services.availability()})


class SolarRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                          viewsets.GenericViewSet):
    """The signed-in resident's solar installation requests."""

    serializer_class = SolarRequestSerializer
    queryset = SolarRequest.objects.all()
    lookup_field = "reference"

    def get_queryset(self):
        qs = SolarRequest.objects.filter(user=self.request.user)
        scope = self.request.query_params.get("scope")
        if scope == "upcoming":
            qs = qs.filter(status__in=SolarRequest.ACTIVE_STATUSES, assessment_date__gte=services.today())
        return qs

    @extend_schema(request=SolarRequestCreateSerializer, responses={201: SolarRequestSerializer})
    def create(self, request, *args, **kwargs):
        inp = SolarRequestCreateSerializer(data=request.data)
        inp.is_valid(raise_exception=True)
        data = inp.validated_data

        # Pre-conditions (ORG-001)
        if data["quarterly_usage_kwh"] <= 0:
            raise PreconditionFailed("Quarterly electricity usage must be greater than 0 kWh.")
        installer = find_installer(data["postcode"])
        if not installer:
            raise NotEligible("Sorry, we don't install solar in that postcode yet.")

        day_str, slot_key = data["slot_id"].split("|")
        day = date.fromisoformat(day_str)
        if day not in services.available_dates():
            raise SlotUnavailable("That site assessment date is no longer available. Please choose another.")
        slot = by_id(TIME_SLOTS, slot_key)

        with transaction.atomic():
            # Lock existing bookings for this slot so two people can't take the last place.
            taken = (SolarRequest.objects.select_for_update()
                     .filter(assessment_date=day, time_slot=slot_key, status__in=SolarRequest.ACTIVE_STATUSES)
                     .count())
            if taken >= services.slot_capacity(day, slot):
                raise SlotUnavailable("Sorry, that time has just filled up. Please choose another.")
            lines = services.price_breakdown(data["system_size"], data["roof_type"], data["storeys"], data["add_ons"])
            obj = SolarRequest.objects.create(
                reference=services.new_reference(),
                user=request.user,
                customer_name=data["customer_name"].strip(),
                customer_email=data["customer_email"],
                customer_phone=data["customer_phone"].strip(),
                address_line=data["address_line"].strip(),
                suburb=data["suburb"].strip().upper(),
                postcode=data["postcode"],
                installer=installer["name"],
                property_type=data["property_type"],
                storeys=data["storeys"],
                roof_type=data["roof_type"],
                quarterly_usage_kwh=data["quarterly_usage_kwh"],
                system_size=data["system_size"],
                add_ons=data["add_ons"],
                total_price=sum(line["amount"] for line in lines),
                assessment_date=day,
                time_slot=slot_key,
                notes=data.get("notes", "").strip(),
            )
            SolarRequestEvent.objects.create(
                request=obj, activity=SolarRequestEvent.Activity.BOOK, status=obj.status, actor="NetZero Hub",
                note=f"Site assessment booked with {obj.installer}.",
            )
        return Response(SolarRequestSerializer(obj).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=SolarRequestSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, reference=None):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if not obj.is_active:
                raise ChangeNotAllowed(f"This request is already {obj.get_status_display().lower()}.")
            obj.status = SolarRequest.Status.CANCELLED
            obj.save(update_fields=["status", "updated_at"])
            SolarRequestEvent.objects.create(request=obj, activity=SolarRequestEvent.Activity.CANCEL,
                                             status=obj.status, actor=obj.customer_name,
                                             note="Cancelled by the customer.")
            services.refund_all(obj)
        return Response(SolarRequestSerializer(obj).data)

    @extend_schema(request=PaymentSerializer, responses=SolarRequestSerializer)
    @action(detail=True, methods=["post"])
    def pay(self, request, reference=None):
        """Pay the 10% deposit, the full amount, or the remaining balance (demo card payment)."""
        inp = PaymentSerializer(data=request.data)
        inp.is_valid(raise_exception=True)
        data = inp.validated_data
        errors = services.card_errors(data["card_number"], data["expiry"].strip(), data["cvc"].strip())
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        if data["card_number"] == services.DECLINED_TEST_CARD:
            raise PaymentDeclined("Your card was declined. Please try a different card.")

        with transaction.atomic():
            obj = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if obj.status == SolarRequest.Status.CANCELLED:
                raise ChangeNotAllowed("This request has been cancelled, so there's nothing to pay.")
            option = next((o for o in services.payment_options(obj) if o["id"] == data["option"]), None)
            if not option:
                raise ChangeNotAllowed("Nothing is due for that option. Refresh the page to see what's owing.")
            services.record_payment(
                obj, kind=data["option"].upper(), amount=option["amount"],
                brand=services.card_brand(data["card_number"]), last4=data["card_number"][-4:],
                actor=obj.customer_name,
            )
        return Response(SolarRequestSerializer(obj).data)


# --------------------------------------------------------------------------------------------
# Admin dashboard (staff only)
# --------------------------------------------------------------------------------------------
class AdminSummaryView(APIView):
    """Headline numbers for the solar admin dashboard."""

    permission_classes = [IsAdminUser]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        today = services.today()
        week_end = today + timedelta(days=7)
        qs = SolarRequest.objects.all()
        by_status = {s: 0 for s, _ in SolarRequest.Status.choices}
        for row in qs.values("status").annotate(n=Count("id")):
            by_status[row["status"]] = row["n"]
        by_size = {s["id"]: 0 for s in SYSTEM_SIZES}
        for row in qs.exclude(status=SolarRequest.Status.CANCELLED).values("system_size").annotate(n=Count("id")):
            by_size[row["system_size"]] = row["n"]
        active = qs.filter(status__in=SolarRequest.ACTIVE_STATUSES)
        return Response({
            "total": qs.count(),
            "by_status": by_status,
            "assessments_today": active.filter(status=SolarRequest.Status.CONFIRMED, assessment_date=today).count(),
            "assessments_next_7_days": active.filter(
                status=SolarRequest.Status.CONFIRMED, assessment_date__gte=today, assessment_date__lt=week_end).count(),
            "pipeline_value": active.aggregate(v=Sum("total_price"))["v"] or 0,
            "installed_value": qs.filter(status=SolarRequest.Status.COMPLETED).aggregate(v=Sum("total_price"))["v"] or 0,
            "payments_received": qs.aggregate(v=Sum("amount_paid"))["v"] or 0,
            "by_payment_status": {
                s: qs.filter(payment_status=s).count() for s, _ in SolarRequest.PaymentStatus.choices
            },
            "by_system_size": [
                {"id": s["id"], "name": s["name"], "count": by_size.get(s["id"], 0)} for s in SYSTEM_SIZES
            ],
        })


class AdminRequestListView(APIView):
    """All customers' solar requests. Filters: ?status=, ?date=YYYY-MM-DD (assessment date), ?q= (search)."""

    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[OpenApiParameter("status", str), OpenApiParameter("date", str), OpenApiParameter("q", str)],
        responses=SolarAdminRequestSerializer(many=True),
    )
    def get(self, request):
        qs = SolarRequest.objects.select_related("user").prefetch_related("events")
        status_filter = request.query_params.get("status")
        if status_filter == "ACTIVE":
            qs = qs.filter(status__in=SolarRequest.ACTIVE_STATUSES)
        elif status_filter:
            qs = qs.filter(status=status_filter)
        day = request.query_params.get("date")
        if day:
            try:
                qs = qs.filter(assessment_date=date.fromisoformat(day))
            except ValueError:
                pass
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(reference__icontains=q) | Q(customer_name__icontains=q) | Q(customer_email__icontains=q)
                | Q(address_line__icontains=q) | Q(suburb__icontains=q) | Q(postcode__icontains=q)
                | Q(user__username__icontains=q)
            )
        return Response(SolarAdminRequestSerializer(qs.order_by("assessment_date", "time_slot"), many=True).data)


class AdminStatusUpdateView(APIView):
    """Move a request to its next stage (site assessed, installed or cancelled), with a note for the customer."""

    permission_classes = [IsAdminUser]

    @extend_schema(request=StatusUpdateSerializer, responses=SolarAdminRequestSerializer)
    def post(self, request, reference):
        obj = SolarRequest.objects.filter(reference=reference).first()
        if not obj:
            return Response({"detail": "Solar request not found."}, status=status.HTTP_404_NOT_FOUND)
        inp = StatusUpdateSerializer(data=request.data)
        inp.is_valid(raise_exception=True)
        new_status = inp.validated_data["status"]
        note = inp.validated_data["note"].strip()
        if new_status not in obj.allowed_transitions():
            raise ChangeNotAllowed(
                f"A request that is '{obj.get_status_display()}' can't be changed to "
                f"'{SolarRequest.Status(new_status).label}'."
            )
        with transaction.atomic():
            obj = SolarRequest.objects.select_for_update().get(pk=obj.pk)
            obj.status = new_status
            if note:
                obj.staff_note = note
            obj.save(update_fields=["status", "staff_note", "updated_at"])
            SolarRequestEvent.objects.create(
                request=obj, activity=STAFF_ACTIVITY[new_status], status=new_status, note=note,
                actor=request.user.get_full_name() or request.user.username,
            )
            if new_status == SolarRequest.Status.CANCELLED:
                services.refund_all(obj)
        return Response(SolarAdminRequestSerializer(obj).data)
