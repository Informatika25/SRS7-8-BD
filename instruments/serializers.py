from rest_framework import serializers
from .models import (
    InstrumentCategory,
    Instrument,
    InstrumentRequest,
    InstrumentRequestEvent
)


class InstrumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstrumentCategory
        fields = ("id", "name")

class InstrumentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = Instrument
        fields = (
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "total_quantity",
            "available_quantity",
            "created_at"
        )
        read_only_fields = ("id", "created_at")

class InstrumentRequestEventSerializer(serializers.ModelSerializer):
    initiator_name = serializers.CharField(
        source="initiator.username",
        read_only=True
    )

    action_display = serializers.CharField(
        source="get_action_display",
        read_only=True
    )

    class Meta:
        model = InstrumentRequestEvent
        fields = (
            "id",
            "request",
            "initiator",
            "initiator_name",
            "action",
            "action_display",
            "created_at",
            "comment",
            "request_id_snapshot",
            "instrument_name_snapshot",
            "quantity_snapshot",
        )
        read_only_fields = fields

class InstrumentRequestSerializer(serializers.ModelSerializer):
    instrument_name = serializers.CharField(
        source="instrument.name",
        read_only=True
    )

    owner_name = serializers.CharField(
        source="owner.username",
        read_only=True
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )

    class Meta:
        model = InstrumentRequest
        fields = (
            "id",
            "instrument",
            "instrument_name",
            "owner",
            "owner_name",
            "quantity",
            "status",
            "status_display",
            "created_at",
            "processed_by",
            "processed_at",
            "rejection_reason"
        )
        read_only_fields = (
            "id",
            "owner",
            "status",
            "created_at",
            "processed_by",
            "processed_at",
            "rejection_reason"
        )

    def validate(self, attrs):

        if self.instance and "status" in self.initial_data:
            raise serializers.ValidationError({
                "status": "Нельзя изменять статус напрямую. Используйте специальные действия."
            })

        instrument = attrs.get(
            "instrument",
            self.instance.instrument if self.instance else None
        )

        quantity = attrs.get(
            "quantity",
            self.instance.quantity if self.instance else None
        )

        if self.instance and self.instance.status != InstrumentRequest.Status.NEW:
            raise serializers.ValidationError(
                "Можно редактировать только новые заявки."
            )

        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({
                "quantity": "Количество инструментов должно быть больше нуля."
            })

        if instrument and quantity is not None:
            if quantity > instrument.available_quantity:
                raise serializers.ValidationError({
                    "quantity": "Запрошенное количество превышает доступное."
                })

        return attrs