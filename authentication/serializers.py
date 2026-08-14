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


class FirstLoginPasswordSetSerializer(serializers.Serializer):
    """İlk giriş - admin tərəfindən yaradılan istifadəçi kodsuz, birbaşa yeni şifrə təyin edir."""
    temp_token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class SelfProfileUpdateSerializer(serializers.ModelSerializer):
    """Şəxsi kabinet - istifadəçinin öz məlumatlarını redaktə etməsi üçün (Image 4).
    Təşkilat, istifadəçi adı və status kimi sahələr buradan dəyişilmir."""

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "phone", "email",
            "fin_kod", "id_card_serial", "department", "position",
        ]
        extra_kwargs = {field: {"required": False} for field in [
            "first_name", "last_name", "phone", "email",
            "fin_kod", "id_card_serial", "department", "position",
        ]}


class UserOrganizationSerializer(serializers.Serializer):
    """Şəxsi kabinet - 'Təşkilat' bölməsi üçün yığcam, read-only görünüş (Image 4)."""
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    voen = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    organization_detail = UserOrganizationSerializer(source="organization", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "username", "email", "phone",
            "organization", "organization_detail", "fin_kod", "id_card_serial",
            "department", "position",
            "is_active", "is_locked", "totp_confirmed", "date_joined",
        ]
        read_only_fields = ["id", "is_locked", "totp_confirmed", "date_joined"]


class UserListSerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> İstifadəçilər siyahısı (Image 2) üçün."""
    full_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.full_name", read_only=True, default="")

    class Meta:
        model = User
        fields = [
            "id", "full_name", "first_name", "last_name", "username", "email", "phone",
            "organization", "organization_name", "fin_kod", "id_card_serial",
            "is_active", "is_locked", "date_joined",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class CreateUserSerializer(serializers.ModelSerializer):
    """Yeni istifadəçi yaratmaq üçün (Image 3-dəki form) - admin/idarəçi tərəfindən istifadə olunur.

    'password' göndərilməsə, təsadüfi şifrə yaradılır və istifadəçiyə şifrə-təyini e-poçtu göndərilir
    (dizaynda parol sahəsi yoxdur - Image 3).
    'modules' - Image 3-dəki 'İcazə veriləcək modulları seçin' + 'Status' (Baxış/Redaktə/Təsdiq)
    hissəsi üçün, [{"module": <id>, "can_view": bool, "can_edit": bool, "can_approve": bool}, ...]
    """
    password = serializers.CharField(write_only=True, trim_whitespace=False, required=False, allow_blank=True)
    modules = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "username", "email", "phone",
            "organization", "fin_kod", "id_card_serial", "password", "modules",
        ]

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> İstifadəçi redaktəsi üçün (Image 2 'Redaktə' / status dəyişimi)."""

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "email", "phone", "organization",
            "fin_kod", "id_card_serial", "is_active",
        ]
        extra_kwargs = {field: {"required": False} for field in [
            "first_name", "last_name", "email", "phone", "organization",
            "fin_kod", "id_card_serial", "is_active",
        ]}


class AdminResetTOTPSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class UnlockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()