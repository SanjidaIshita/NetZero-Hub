"""Counts for the "My Services Dashboard" page: one number per NetZero Hub service."""
from django.apps import apps
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView


class DashboardView(APIView):
    """Active requests the signed-in user has in each service."""

    @extend_schema(responses=inline_serializer("DashboardCounts", {
        "recycling_count": serializers.IntegerField(),
        "environment_count": serializers.IntegerField(),
        "solar_count": serializers.IntegerField(),
    }))
    def get(self, request):
        user = request.user
        counts = {"recycling_count": 0, "environment_count": 0, "solar_count": 0}

        if apps.is_installed("recycling"):
            from recycling.models import Booking
            counts["recycling_count"] = Booking.objects.filter(user=user, status__in=Booking.ACTIVE_STATUSES).count()

        if apps.is_installed("solar"):
            from solar.models import SolarRequest
            counts["solar_count"] = SolarRequest.objects.filter(
                user=user, status__in=SolarRequest.ACTIVE_STATUSES).count()

        # The environment protection service adds its own count here when its app is added.
        return Response(counts)
