from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .dashboard import DashboardView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("recycling.urls")),
    path("api/v1/solar/", include("solar.urls")),
    path("api/v1/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
