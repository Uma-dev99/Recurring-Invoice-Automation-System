from rest_framework import serializers

from apps.operations.models import AuditLog
from apps.operations.selectors import SYSTEM_ACTOR


class _ActorSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.email


class AuditLogSerializer(serializers.ModelSerializer):
    # null = done by the system (background jobs), not by a person.
    actor = _ActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = ["id", "created_at", "action", "entity_type", "entity_id", "actor", "changes"]
        read_only_fields = fields


class AuditLogQuerySerializer(serializers.Serializer):
    action = serializers.CharField(required=False, max_length=100)
    entity_type = serializers.CharField(required=False, max_length=100)
    entity_id = serializers.UUIDField(required=False)
    actor = serializers.CharField(
        required=False, help_text=f'A user id, or "{SYSTEM_ACTOR}" for background jobs.'
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate_actor(self, value: str) -> str:
        if value != SYSTEM_ACTOR:
            serializers.UUIDField().to_internal_value(value)  # raises a clear error if not
        return value

    def validate(self, attrs):
        if (
            attrs.get("date_from")
            and attrs.get("date_to")
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError({"date_to": ["Must be on or after the start date."]})
        return attrs


class AuditFilterOptionsSerializer(serializers.Serializer):
    actions = serializers.ListField(child=serializers.CharField())
    entity_types = serializers.ListField(child=serializers.CharField())
