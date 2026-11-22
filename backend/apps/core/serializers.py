from rest_framework import serializers


class RejectUnknownFieldsMixin:
    """Make an input serializer refuse fields it does not declare.

    DRF ignores unknown keys by default. For a write endpoint that is misleading: a
    client sending {"status": "INACTIVE"} to an edit endpoint would get 200 OK while
    nothing changed. With this mixin it gets 400 and an explanation per field.
    """

    def validate(self, attrs):
        unknown = set(getattr(self, "initial_data", {}) or {}) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: ["This field is not allowed here."] for field in sorted(unknown)}
            )
        return super().validate(attrs)
