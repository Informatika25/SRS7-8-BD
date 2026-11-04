from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include

from tickets.views import register


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", healthz),
    path("admin/", admin.site.urls),
    path("accounts/register/", register, name="register"),
    path("accounts/", include('django.contrib.auth.urls')),
    path("", include("tickets.urls")),
    path("api/", include("instruments.urls")),
]
