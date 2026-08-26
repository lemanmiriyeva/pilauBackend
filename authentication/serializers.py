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
    """İstifadəçi adı VƏ YA e-poçt ünvanı ilə şifrə bərpa kodu tələb etmək üçün."""
    identifier = serializers.CharField()


class ForgotPasswordConfirmSerializer(serializers.Serializer):
    """identifier - əvvəlki addımda göndərilən eyni istifadəçi adı/e-poçt."""
    identifier = serializers.CharField()
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
    Təşkilat, istifadəçi adı, FİN kod və status kimi sahələr buradan dəyişilmir
    (FİN kod sistem tərəfindən verilən identifikatordur, UI-da disabled göstərilir).

    department/position artıq sərbəst mətn deyil, FK-dir (bax User modeli) - buraya YALNIZ
    istifadəçinin öz təşkilatına aid OrganizationDepartment/OrganizationPosition seçilə bilər,
    başqa təşkilatın siyahısından ID göndərmək rədd edilir."""

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "phone", "email",
            "fin_kod", "id_card_serial", "department", "position",
        ]
        read_only_fields = ["fin_kod"]
        extra_kwargs = {field: {"required": False} for field in [
            "first_name", "last_name", "phone", "email",
            "id_card_serial", "department", "position",
        ]}

    def _validate_own_org(self, value, field_label):
        if value is None:
            return value
        user = self.instance
        if user is None or not user.organization_id or value.organization_id != user.organization_id:
            raise serializers.ValidationError(f"Bu {field_label} sizin təşkilatınıza aid deyil.")
        return value

    def validate_department(self, value):
        return self._validate_own_org(value, "departament")

    def validate_position(self, value):
        return self._validate_own_org(value, "vəzifə")


class UserOrganizationSerializer(serializers.Serializer):
    """Şəxsi kabinet - 'Təşkilat' bölməsi üçün yığcam, read-only görünüş (Image 4).
    Employee-nin öz təşkilatı haqqında bilməli olduğu BÜTÜN əsas sahələr - yalnız
    full_name/voen deyil, əlaqə məlumatları da daxil olmaqla."""
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    voen = serializers.CharField()
    state_reg_number = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()


class UserDepartmentSerializer(serializers.Serializer):
    """Şəxsi kabinet - departament seçimini oxunaqlı ad (name) ilə göstərmək üçün.
    User.department artıq sərbəst mətn deyil, FK-dir - frontend-in oxunaqlı ad görməsi
    üçün department_detail (bax UserSerializer) kimi əlavə olunur."""
    id = serializers.IntegerField()
    name = serializers.CharField()


class UserPositionSerializer(serializers.Serializer):
    """Şəxsi kabinet - vəzifə seçimini oxunaqlı ad (name) ilə göstərmək üçün."""
    id = serializers.IntegerField()
    name = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    organization_detail = UserOrganizationSerializer(source="organization", read_only=True)
    department_detail = UserDepartmentSerializer(source="department", read_only=True)
    position_detail = UserPositionSerializer(source="position", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "organization",
            "organization_detail",
            "department",
            "department_detail",
            "position",
            "position_detail",
            "birth_date",
            "fin_kod",
            "id_card_serial",
            "is_org_admin",
            "is_staff",
            "is_active",
            "is_locked",
            "totp_confirmed",
            "date_joined",
        ]
        read_only_fields = ["id", "is_org_admin", "is_staff", "is_locked", "totp_confirmed", "date_joined"]


class UserListSerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> İstifadəçilər siyahısı (Image 2) üçün."""
    full_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.full_name", read_only=True, default="")

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "organization",
            "organization_name",
            "department",
            "position",
            "birth_date",
            "fin_kod",
            "id_card_serial",
            "is_org_admin",
            "is_active",
            "is_locked",
            "date_joined",
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
    approver_doc_types = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "organization",
            "department",
            "position",
            "birth_date",
            "fin_kod",
            "id_card_serial",
            "is_org_admin",
            "password",
            "modules",
            "approver_doc_types",
        ]

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def validate(self, attrs):
        organization = attrs.get("organization")
        department = attrs.get("department")
        position = attrs.get("position")

        if department and organization:
            if department.organization_id != organization.id:
                raise serializers.ValidationError({
                    "department": "Departament seçilmiş quruma aid deyil."
                })

        if position and organization:
            if position.organization_id != organization.id:
                raise serializers.ValidationError({
                    "position": "Vəzifə seçilmiş quruma aid deyil."
                })

        return attrs


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """İnzibatçı Paneli -> İstifadəçi redaktəsi üçün (Image 2 'Redaktə' / status dəyişimi).

    QEYD: 'organization' və 'is_org_admin' sahələri buradadır, lakin UserAdminDetailView
    yalnız is_staff/is_superuser olan sorğuçular üçün onların dəyişilməsinə icazə verir - qurum
    admini (is_org_admin=True, is_staff=False) öz təşkilatındakı istifadəçiləri redaktə edə bilər,
    amma onları başqa təşkilata köçürə və ya özünə/başqasına 'qurum admini' statusu verə bilməz
    (bax: authentication/views.py -> UserAdminDetailView.perform_update)."""

    approver_doc_types = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "organization",
            "department",
            "position",
            "birth_date",
            "fin_kod",
            "id_card_serial",
            "is_org_admin",
            "is_active",
            "approver_doc_types",
        ]
        extra_kwargs = {field: {"required": False} for field in [
            "first_name", "last_name", "email", "phone", "organization",
            "fin_kod", "id_card_serial", "is_org_admin", "is_active",
        ]}

    def validate(self, attrs):
        organization = attrs.get(
            "organization",
            self.instance.organization if self.instance else None
        )

        department = attrs.get("department")
        position = attrs.get("position")

        if department and organization:
            if department.organization_id != organization.id:
                raise serializers.ValidationError({
                    "department": "Departament seçilmiş quruma aid deyil."
                })

        if position and organization:
            if position.organization_id != organization.id:
                raise serializers.ValidationError({
                    "position": "Vəzifə seçilmiş quruma aid deyil."
                })

        return attrs


class AdminResetTOTPSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class TOTPRequestAdminHelpSerializer(serializers.Serializer):
    """2FA cihazini itirmis istifadeci - self-service bərpa üçün 1-ci addim:
    username ilə e-poçtuna sıfırlama kodu göndərilir (bax: TOTPRequestAdminHelpView)."""
    username = serializers.CharField()


class TOTPAdminHelpConfirmSerializer(serializers.Serializer):
    """2-ci addim: eyni username + e-poçta gələn kod. Kod doğrudursa 2FA sıfırlanır,
    istifadəçi növbəti girişdə yenidən QR quracaq (bax: TOTPAdminHelpConfirmView)."""
    username = serializers.CharField()
    code = serializers.CharField(max_length=6)


class UnlockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()