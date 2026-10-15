from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.register("bookings", views.BookingViewSet, basename="booking")

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("waste-types/", views.WasteTypeListView.as_view(), name="waste-types"),
    path("service-areas/check/", views.ServiceAreaCheckView.as_view(), name="service-area-check"),
    path("availability/", views.AvailabilityView.as_view(), name="availability"),
    path("provider/collections/", views.ProviderCollectionListView.as_view(), name="provider-collections"),
    path(
        "provider/collections/<str:reference>/completed/",
        views.CollectionCompletedView.as_view(),
        name="collection-completed",
    ),
    path(
        "provider/collections/<str:reference>/missed/",
        views.CollectionMissedView.as_view(),
        name="collection-missed",
    ),
    path("integration/bookings/", views.IntegrationBookingListView.as_view(), name="integration-bookings"),
    path(
        "integration/bookings/<str:reference>/",
        views.IntegrationBookingDetailView.as_view(),
        name="integration-booking-detail",
    ),
] + router.urls
