from rest_framework import serializers

from apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    """Validates the *shape* of login input only. Checking the password is the view's job."""

    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class CurrentUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "is_staff"]
        read_only_fields = fields

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.email
