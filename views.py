from django.contrib.auth import authenticate
from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, WasteType
from .permissions import HasIntegrationKey, IsProviderOrStaff
from .serializers import (
    AvailabilityQuerySerializer,
    BookingCreateSerializer,
    BookingOutputSerializer,
    BookingSerializer,
    LoginSerializer,
    MissedCollectionSerializer,
    NotificationSerializer,
    ProviderCollectionSerializer,
    ProviderContactSerializer,
    QuoteSerializer,
    RegisterSerializer,
    RescheduleSerializer,
    SlotSerializer,
    UserSerializer,
    WasteTypeSerializer,
)
from .services import orchestrator
from .services import provider as provider_api

BOOKING_RELATED = ("waste_type", "provider", "slot", "payment", "user")


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: dict})
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok", "service": "WMS-002", "time": timezone.now()})


# --- auth -----------------------------------------------------------------------------------


def _token_response(user, http_status=status.HTTP_200_OK):
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data}, status=http_status)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _token_response(serializer.save(), status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise AuthenticationFailed("Incorrect username or password.")
        return _token_response(user)


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


# --- reference data ---------------------------------------------------------------------------


class WasteTypeListView(ListAPIView):
    """Supported waste types. Pass ?postcode= to list only those collected in that area."""

    permission_classes = [AllowAny]
    serializer_class = WasteTypeSerializer
    pagination_class = None

    @extend_schema(parameters=[OpenApiParameter("postcode", str, required=False)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = WasteType.objects.filter(active=True)
        postcode = self.request.query_params.get("postcode")
        if postcode:
            area = provider_api.check_service_area(postcode)
            qs = qs.filter(providers=area.provider) if area else qs.none()
        return qs


class ServiceAreaCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(parameters=[OpenApiParameter("postcode", str, required=True)], responses={200: dict})
    def get(self, request):
        postcode = request.query_params.get("postcode", "")
        area = provider_api.check_service_area(postcode)
        if area is None:
            return Response({"postcode": postcode, "eligible": False})
        return Response(
            {
                "postcode": area.postcode,
                "eligible": True,
                "suburb": area.suburb,
                "provider": ProviderContactSerializer(area.provider).data,
            }
        )


class AvailabilityView(APIView):
    """checkAvailability: validate session + service area, then list free slots."""

    @extend_schema(parameters=[AvailabilityQuerySerializer], responses={200: dict})
    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        area, slots = orchestrator.check_availability(request.user, **query.validated_data)
        return Response(
            {
                "postcode": area.postcode,
                "suburb": area.suburb,
                "provider": ProviderContactSerializer(area.provider).data,
                "slots": SlotSerializer(slots, many=True).data,
            }
        )


# --- resident bookings (IRecyclingBooking) ---------------------------------------------------


class BookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer
    lookup_field = "reference"
    lookup_value_regex = "[A-Za-z0-9-]+"
    pagination_class = None

    def get_queryset(self):
        qs = (
            Booking.objects.filter(user=self.request.user)
            .select_related(*BOOKING_RELATED)
            .prefetch_related("events", "notifications")
        )
        scope = self.request.query_params.get("scope")
        today = timezone.localdate()
        if scope == "upcoming":
            qs = qs.filter(status__in=Booking.ACTIVE_STATUSES, slot__date__gte=today).order_by("slot__date")
        elif scope == "past":
            qs = qs.exclude(status__in=Booking.ACTIVE_STATUSES, slot__date__gte=today)
        return qs

    @extend_schema(parameters=[OpenApiParameter("scope", str, enum=["upcoming", "past"], required=False)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def _detail(self, booking, http_status=status.HTTP_200_OK):
        booking = Booking.objects.select_related(*BOOKING_RELATED).get(pk=booking.pk)
        return Response(BookingSerializer(booking).data, status=http_status)

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def create(self, request):
        """createBooking: reserve slot, take payment if chargeable, confirm and notify."""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = orchestrator.create_booking(request.user, **serializer.validated_data)
        return self._detail(booking, status.HTTP_201_CREATED)

    @extend_schema(request=QuoteSerializer, responses={200: dict})
    @action(detail=False, methods=["post"])
    def quote(self, request):
        """Fee quote shown to the resident before confirming (standard recycling is free)."""
        serializer = QuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fee, breakdown = orchestrator.quote(**serializer.validated_data)
        return Response(
            {"fee": str(fee), "currency": "AUD", "chargeable": fee > 0, "breakdown": breakdown}
        )

    @extend_schema(request=RescheduleSerializer, responses={200: BookingSerializer})
    @action(detail=True, methods=["post"])
    def reschedule(self, request, reference=None):
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = orchestrator.reschedule_booking(self.get_object(), serializer.validated_data["slot_id"])
        return self._detail(booking)

    @extend_schema(request=None, responses={200: BookingSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, reference=None):
        booking = orchestrator.cancel_booking(self.get_object())
        return self._detail(booking)

    @extend_schema(responses={200: BookingOutputSerializer})
    @action(detail=True, methods=["get"])
    def output(self, request, reference=None):
        """The WMS-002 service output for this booking."""
        return Response(BookingOutputSerializer(self.get_object()).data)

    @extend_schema(responses={200: NotificationSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def notifications(self, request, reference=None):
        return Response(NotificationSerializer(self.get_object().notifications.all(), many=True).data)


# --- provider (IProviderScheduling / ICollectionStatus callback) ------------------------------


def _provider_bookings(request):
    qs = Booking.objects.select_related(*BOOKING_RELATED).exclude(provider=None)
    if getattr(request, "provider", None) is not None:
        qs = qs.filter(provider=request.provider)
    return qs


class ProviderCollectionListView(APIView):
    """Collection run sheet for the provider: active bookings for a date (default today)."""

    permission_classes = [IsProviderOrStaff]

    @extend_schema(
        parameters=[OpenApiParameter("date", str, required=False, description="YYYY-MM-DD")],
        responses={200: ProviderCollectionSerializer(many=True)},
    )
    def get(self, request):
        qs = _provider_bookings(request).filter(status__in=Booking.ACTIVE_STATUSES)
        day = request.query_params.get("date")
        if day:
            qs = qs.filter(slot__date=day)
        else:
            qs = qs.filter(slot__date__gte=timezone.localdate())
        qs = qs.order_by("slot__date", "slot__start_time", "postcode")[:500]
        return Response(ProviderCollectionSerializer(qs, many=True).data)


class CollectionCompletedView(APIView):
    permission_classes = [IsProviderOrStaff]

    @extend_schema(request=None, responses={200: BookingOutputSerializer})
    def post(self, request, reference):
        booking = get_object_or_404(_provider_bookings(request), reference=reference)
        booking = orchestrator.collection_completed(booking)
        return Response(BookingOutputSerializer(booking).data)


class CollectionMissedView(APIView):
    permission_classes = [IsProviderOrStaff]

    @extend_schema(request=MissedCollectionSerializer, responses={200: BookingOutputSerializer})
    def post(self, request, reference):
        serializer = MissedCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = get_object_or_404(_provider_bookings(request), reference=reference)
        booking = orchestrator.collection_missed(booking, serializer.validated_data["reason"])
        return Response(BookingOutputSerializer(booking).data)


# --- integration API: WMS-002 outputs for other services --------------------------------------


class IntegrationBookingListView(ListAPIView):
    """Feed of WMS-002 service outputs for downstream services (X-API-Key)."""

    authentication_classes = []
    permission_classes = [HasIntegrationKey]
    serializer_class = BookingOutputSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, required=False),
            OpenApiParameter("collection_date", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("postcode", str, required=False),
            OpenApiParameter("updated_since", str, required=False, description="ISO-8601 timestamp"),
            OpenApiParameter("limit", int, required=False, description="Max 500, default 100"),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        qs = Booking.objects.select_related(*BOOKING_RELATED).order_by("-updated_at")
        if params.get("status"):
            qs = qs.filter(status=params["status"].upper())
        if params.get("collection_date"):
            qs = qs.filter(slot__date=params["collection_date"])
        if params.get("postcode"):
            qs = qs.filter(postcode=params["postcode"])
        if params.get("updated_since"):
            qs = qs.filter(updated_at__gte=params["updated_since"])
        try:
            limit = min(max(int(params.get("limit", 100)), 1), 500)
        except ValueError:
            limit = 100
        return qs[:limit]


class IntegrationBookingDetailView(RetrieveAPIView):
    authentication_classes = []
    permission_classes = [HasIntegrationKey]
    serializer_class = BookingOutputSerializer
    lookup_field = "reference"
    queryset = Booking.objects.select_related(*BOOKING_RELATED)
