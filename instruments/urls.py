from rest_framework.routers import DefaultRouter

from .views import (
    InstrumentCategoryViewSet,
    InstrumentViewSet,
    InstrumentRequestViewSet
)

router = DefaultRouter()

router.register(
    "instrument-categories",
    InstrumentCategoryViewSet,
    basename="instrument-category"
)

router.register(
    "instruments",
    InstrumentViewSet,
    basename="instrument"
)

router.register(
    "instrument-requests",
    InstrumentRequestViewSet,
    basename="instrument-request"
)

urlpatterns = router.urls