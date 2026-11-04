from django.db import models
from django.conf import settings

# Create your models here.

class InstrumentCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Instrument(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        InstrumentCategory,
        on_delete=models.PROTECT,
        related_name="instruments"
    )
    total_quantity = models.PositiveIntegerField()
    available_quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class InstrumentRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        RETURNED = "returned", "Возвращена"

    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="requests"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="instrument_requests"
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW
    )
    created_at = models.DateTimeField(auto_now_add=True)

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_instrument_requests"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f"Заявка №{self.id} — {self.instrument.name}"

class InstrumentRequestEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Создана"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        RETURNED = "returned", "Возвращена"
        EDITED = "edited", "Изменена"
        DELETED = "deleted", "Удалена"

    request = models.ForeignKey(
        InstrumentRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events"
    )

    request_id_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True
    )
    instrument_name_snapshot = models.CharField(
        max_length=50,
        blank=True
    )
    quantity_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instrument_request_events"
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices
    )
    created_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    def __str__(self):
        request_id = self.request_id or self.request_id_snapshot
        return (
            f"{self.get_action_display()} — "
            f"заявка №{request_id or 'неизвестно'}"
        )