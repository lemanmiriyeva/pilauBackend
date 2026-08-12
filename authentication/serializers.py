from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class TOTPVerifySerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    code = serializers.CharField(max_length=10)


class TOTPSetupConfirmSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    code = serializers.CharField(max_length=10)


class ForgotPasswordRequestSerializer(serializers.Serializer):
    username = serializers.CharField()


class ForgotPasswordConfirmSerializer(serializers.Serializer):
    username = serializers.CharField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "username", "email", "phone",
            "organization", "fin_kod", "id_card_serial",
            "is_active", "is_locked", "totp_confirmed", "date_joined",
        ]
        read_only_fields = ["id", "is_locked", "totp_confirmed", "date_joined"]


class CreateUserSerializer(serializers.ModelSerializer):
    """Yeni istifadəçi yaratmaq üçün (Image 1-dəki form) - admin/idarəçi tərəfindən istifadə olunur."""
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "username", "email", "phone",
            "organization", "fin_kod", "id_card_serial", "password",
        ]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AdminResetTOTPSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class UnlockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
