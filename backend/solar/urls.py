from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("requests", views.SolarRequestViewSet, basename="solar-request")

# Mounted at /api/v1/solar/
urlpatterns = [
    path("options/", views.OptionsView.as_view(), name="solar-options"),
    path("postcode/", views.PostcodeCheckView.as_view(), name="solar-postcode"),
    path("recommend/", views.RecommendView.as_view(), name="solar-recommend"),
    path("availability/", views.AvailabilityView.as_view(), name="solar-availability"),
] + router.urls
