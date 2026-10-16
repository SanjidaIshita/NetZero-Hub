from datetime import date

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from recycling.services.exceptions import ChangeNotAllowed, NotEligible, ServiceError, SlotUnavailable

from . import services
from .catalogue import ADD_ONS, PROPERTY_TYPES, ROOF_TYPES, STOREYS, SUBURBS, SYSTEM_SIZES, TIME_SLOTS, by_id, find_installer
from .models import SolarRequest
from .serializers import SolarRequestCreateSerializer, SolarRequestSerializer


class PreconditionFailed(ServiceError):
    status_code = 400
    code = "precondition_failed"


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
        return Response(SolarRequestSerializer(obj).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=SolarRequestSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, reference=None):
        obj = self.get_object()
        if not obj.is_active:
            raise ChangeNotAllowed(f"This request is already {obj.get_status_display().lower()}.")
        obj.status = SolarRequest.Status.CANCELLED
        obj.save(update_fields=["status", "updated_at"])
        return Response(SolarRequestSerializer(obj).data)
