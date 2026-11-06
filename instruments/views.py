from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    InstrumentCategory,
    Instrument,
    InstrumentRequest,
    InstrumentRequestEvent
)
from .serializers import (
    InstrumentCategorySerializer,
    InstrumentSerializer,
    InstrumentRequestSerializer,
    InstrumentRequestEventSerializer
)


class InstrumentCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InstrumentCategory.objects.all()
    serializer_class = InstrumentCategorySerializer
    permission_classes = [IsAuthenticated]


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Instrument.objects.select_related("category").all()
    serializer_class = InstrumentSerializer
    permission_classes = [IsAuthenticated]


class InstrumentRequestViewSet(viewsets.ModelViewSet):
    serializer_class = InstrumentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            queryset = InstrumentRequest.objects.all()
        else:
            queryset = InstrumentRequest.objects.filter(
                owner=self.request.user
            )

        queryset = queryset.select_related(
            "instrument",
            "instrument__category",
            "owner"
        )

        request_status = self.request.query_params.get("status")
        if request_status:
            queryset = queryset.filter(status=request_status)

        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(
                instrument__category_id=category
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        with transaction.atomic():
            instrument_request = serializer.save(
                owner=self.request.user
            )

            InstrumentRequestEvent.objects.create(
                request=instrument_request,
                initiator=self.request.user,
                action=InstrumentRequestEvent.Action.CREATED,
                comment="Заявка создана."
            )

    def perform_update(self, serializer):
        if serializer.instance.owner != self.request.user:
            raise PermissionDenied(
                "Вы можете изменять только свои заявки."
            )

        old_quantity = serializer.instance.quantity
        old_instrument_id = serializer.instance.instrument_id

        with transaction.atomic():
            updated_request = serializer.save()

            if (
                    updated_request.quantity != old_quantity
                    or updated_request.instrument_id != old_instrument_id
            ):
                InstrumentRequestEvent.objects.create(
                    request=updated_request,
                    initiator=self.request.user,
                    action=InstrumentRequestEvent.Action.EDITED,
                    comment=(
                        f"Заявка изменена. "
                        f"Количество: {old_quantity} → "
                        f"{updated_request.quantity}."
                    )
                )

    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            raise PermissionDenied(
                "Нельзя удалить чужую заявку."
            )

        if instance.status != InstrumentRequest.Status.NEW:
            raise PermissionDenied(
                "Можно удалить только новую заявку."
            )

        with transaction.atomic():
            # Сохраняем данные во всех старых событиях
            instance.events.update(
                request_id_snapshot=instance.id,
                instrument_name_snapshot=instance.instrument.name,
                quantity_snapshot=instance.quantity
            )

            # Создаём событие об удалении
            InstrumentRequestEvent.objects.create(
                request=instance,
                request_id_snapshot=instance.id,
                instrument_name_snapshot=instance.instrument.name,
                quantity_snapshot=instance.quantity,
                initiator=self.request.user,
                action=InstrumentRequestEvent.Action.DELETED,
                comment="Заявка удалена пользователем."
            )

            # Удаляем саму заявку
            instance.delete()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.is_staff:
            raise PermissionDenied(
                "Только сотрудник может одобрять заявки."
            )

        with transaction.atomic():
            instrument_request = self.get_object()

            instrument_request = InstrumentRequest.objects.select_for_update().get(
                pk=instrument_request.pk
            )

            if instrument_request.status != InstrumentRequest.Status.NEW:
                raise ValidationError(
                    "Можно одобрить только новую заявку."
                )

            instrument = Instrument.objects.select_for_update().get(
                pk=instrument_request.instrument_id
            )

            if instrument_request.quantity > instrument.available_quantity:
                raise ValidationError(
                    "Недостаточно инструментов в наличии."
                )

            instrument.available_quantity -= instrument_request.quantity
            instrument.save(update_fields=["available_quantity"])

            instrument_request.status = InstrumentRequest.Status.APPROVED
            instrument_request.processed_by = request.user
            instrument_request.processed_at = timezone.now()
            instrument_request.save()

            InstrumentRequestEvent.objects.create(
                request=instrument_request,
                initiator=request.user,
                action=InstrumentRequestEvent.Action.APPROVED,
                comment="Заявка одобрена."
            )

        return Response(
            InstrumentRequestSerializer(instrument_request).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not request.user.is_staff:
            raise PermissionDenied(
                "Только сотрудник может отклонять заявки."
            )

        reason = request.data.get("reason", "").strip()

        if not reason:
            raise ValidationError(
                "Необходимо указать причину отказа."
            )

        with transaction.atomic():
            instrument_request = self.get_object()

            instrument_request = InstrumentRequest.objects.select_for_update().get(
                pk=instrument_request.pk
            )

            if instrument_request.status != InstrumentRequest.Status.NEW:
                raise ValidationError(
                    "Можно отклонить только новую заявку."
                )

            instrument_request.status = InstrumentRequest.Status.REJECTED
            instrument_request.processed_by = request.user
            instrument_request.processed_at = timezone.now()
            instrument_request.rejection_reason = reason
            instrument_request.save()

            InstrumentRequestEvent.objects.create(
                request=instrument_request,
                initiator=request.user,
                action=InstrumentRequestEvent.Action.REJECTED,
                comment=reason
            )

        return Response(
            InstrumentRequestSerializer(instrument_request).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def return_instrument(self, request, pk=None):
        if not request.user.is_staff:
            raise PermissionDenied(
                "Только сотрудник может оформлять возврат."
            )
        with transaction.atomic():
            instrument_request = self.get_object()
            instrument_request = InstrumentRequest.objects.select_for_update().get(
                pk=instrument_request.pk
            )
            if instrument_request.status != InstrumentRequest.Status.APPROVED:
                raise ValidationError(
                    "Можно вернуть только одобренную заявку."
                )
            instrument = Instrument.objects.select_for_update().get(
                pk=instrument_request.instrument_id
            )
            instrument.available_quantity += instrument_request.quantity
            instrument.save(update_fields=["available_quantity"])
            instrument_request.status = InstrumentRequest.Status.RETURNED
            instrument_request.processed_by = request.user
            instrument_request.processed_at = timezone.now()
            instrument_request.save()
            InstrumentRequestEvent.objects.create(
                request=instrument_request,
                initiator=request.user,
                action=InstrumentRequestEvent.Action.RETURNED,
                comment="Инструменты возвращены."
            )
        return Response(
            InstrumentRequestSerializer(instrument_request).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        instrument_request = self.get_object()

        events = instrument_request.events.select_related(
            "initiator"
        ).order_by("created_at")

        serializer = InstrumentRequestEventSerializer(
            events,
            many=True
        )

        return Response(serializer.data)



