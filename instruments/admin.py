from django.contrib import admin
from .models import (
    InstrumentCategory,
    Instrument,
    InstrumentRequest,
    InstrumentRequestEvent
)

@admin.register(InstrumentCategory)
class InstrumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "category",
        "total_quantity", "available_quantity", "created_at"
    )
    list_filter = ("category",)
    search_fields = ("name",)

@admin.register(InstrumentRequest)
class InstrumentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "instrument", "owner",
        "quantity", "status", "created_at"
    )
    list_filter = ("status", "instrument__category")
    search_fields = ("instrument__name", "owner__username")

@admin.register(InstrumentRequestEvent)
class InstrumentRequestEventAdmin(admin.ModelAdmin):
    list_display = (
        "id", "request", "initiator",
        "action", "created_at"
    )
    list_filter = ("action",)
    search_fields = (
        "request__id",
        "initiator__username",
        "comment",
    )