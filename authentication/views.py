from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
import pyotp

from organizations.permissions import IsStaffOrOrgAdmin, is_full_admin, scoped_organization_ids

from .models import PasswordResetCode, User
from .serializers import (
    AdminResetTOTPSerializer,
    ChangePasswordSerializer,
    CreateUserSerializer,
    FirstLoginPasswordSetSerializer,
    ForgotPasswordConfirmSerializer,
    ForgotPasswordRequestSerializer,
    LoginSerializer,
    SelfProfileUpdateSerializer,
    TOTPRequestAdminHelpSerializer,
    TOTPSetupConfirmSerializer,
    TOTPVerifySerializer,
    UnlockUserSerializer,
    UserAdminUpdateSerializer,
    UserListSerializer,
    UserSerializer,
)
from .utils import (
    decode_temp_token,
    generate_numeric_code,
    get_client_ip,
    hash_code,
    issue_jwt_pair,
    issue_short_lived_token,
    log_security_event,
    send_mail_to,
)

GENERIC_LOGIN_ERROR = {"detail": "İstifadəçi adı və ya şifrə yanlışdır."}
GENERIC_FORGOT_PASSWORD_RESPONSE = {
    "detail": "Əgər bu istifadəçi adı və ya elektron poçt ünvanı mövcuddursa, qeydiyyatdan keçmiş elektron poçt ünvanına kod göndərildi."
}


class LoginView(APIView):
    """
    1-ci addim: username/password.
    Netice: ya 'totp_setup_required' (ilk giris), ya da 'totp_required' (normal giris).
    Access/refresh token BURDA verilmir - yalnix TOTP tesdiqinden sonra.
    """
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        ip = get_client_ip(request)

        user = User.objects.filter(username=username).first()

        if user and user.is_locked:
            log_security_event("LOGIN_BLOCKED_LOCKED", user=user, ip=ip)
            return Response(
                {"detail": "Hesabınız bloklanıb. Administrator ilə əlaqə saxlayın.",
                 "admin_contact_email": settings.ADMIN_CONTACT_EMAIL,
                 "admin_contact_phone": settings.ADMIN_CONTACT_PHONE},
                status=status.HTTP_423_LOCKED,
            )

        if not user or not user.is_active or not user.check_password(password):
            if user and user.is_active:
                user.register_failed_login()
                log_security_event(
                    "LOGIN_FAILED", user=user, ip=ip,
                    extra=f"attempt={user.failed_login_attempts}",
                )
            else:
                log_security_event("LOGIN_FAILED_UNKNOWN_USER", ip=ip, extra=f"username={username}")
            return Response(GENERIC_LOGIN_ERROR, status=status.HTTP_401_UNAUTHORIZED)

        user.reset_failed_login()
        log_security_event("LOGIN_PASSWORD_OK", user=user, ip=ip)

        return Response(_next_login_step_response(user))


def _next_login_step_response(user) -> dict:
    """Şifrə yoxlanışından sonra növbəti addımı müəyyən edir.

    QEYD: 'must_change_password' YALNIZ istifadəçi admin tərəfindən yaradılarkən (CreateUserView)
    True olur - və yaradılan istifadəçinin 2FA-sı da hələ qurulmayıb olur. Ona görə şifrə təyini
    addımı BURADA yoxlanılmır: axın həmişə əvvəlcə 2FA qurulmasına yönləndirir, şifrə təyini isə
    2FA təsdiqləndikdən SONRA soruşulur (bax TOTPSetupConfirmView) - beləliklə admin tərəfindən
    verilmiş müvəqqəti şifrə ilə daxil olan istifadəçi əvvəlcə 2FA-nı təsdiqləyir, sonra öz yeni
    şifrəsini təyin edir."""
    if not user.totp_confirmed:
        temp_token = issue_short_lived_token(user, purpose="totp_setup")
        return {"step": "totp_setup_required", "temp_token": temp_token}

    temp_token = issue_short_lived_token(user, purpose="totp_verify")
    return {"step": "totp_required", "temp_token": temp_token}


class FirstLoginPasswordSetView(APIView):
    """İlk giriş: admin tərəfindən yaradılan istifadəçi 2FA-nı qurub təsdiqlədikdən SONRA
    (bax TOTPSetupConfirmView) öz yeni şifrəsini təyin edir. Bu nöqtəyə çatan istifadəçinin 2FA-sı
    artıq bu sessiyada təsdiqləndiyi üçün (temp_token purpose='password_change' yalnız
    TOTPSetupConfirmView tərəfindən verilir) - şifrə təyinatından sonra birbaşa tam giriş
    (access/refresh) verilir, yenidən 2FA soruşulmur."""
    permission_classes = [AllowAny]
    throttle_scope = "totp_verify"

    def post(self, request):
        serializer = FirstLoginPasswordSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = decode_temp_token(serializer.validated_data["temp_token"], expected_purpose="password_change")
        if not user:
            return Response({"detail": "Sessiya bitib, yenidən daxil olun."}, status=401)

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        log_security_event("FIRST_LOGIN_PASSWORD_SET", user=user, ip=get_client_ip(request))
        send_mail_to(
            user.email, "Şifrəniz təyin edildi",
            "Hesabınız üçün yeni şifrə uğurla təyin edildi.",
        )

        access, refresh = issue_jwt_pair(user)
        return Response({
            "step": "done",
            "access": access,
            "refresh": refresh,
            "user": UserSerializer(user).data,
        })


class TOTPSetupBeginView(APIView):
    """İlk giriş: QR kod üçün gizli açar generasiya edir (hələ təsdiqlənməyib)."""
    permission_classes = [AllowAny]

    def post(self, request):
        user = decode_temp_token(request.data.get("temp_token"), expected_purpose="totp_setup")
        if not user:
            return Response({"detail": "Sessiya bitib, yenidən daxil olun."}, status=401)

        secret = pyotp.random_base32()
        user.set_totp_secret(secret)
        user.save(update_fields=["totp_secret_encrypted"])

        uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="Secure Project"
        )
        return Response({"qr_uri": uri, "manual_key": secret})


class TOTPSetupConfirmView(APIView):
    """İstifadəçi authenticator app-dən aldığı ilk kodu göndərir - setup tamamlanır."""
    permission_classes = [AllowAny]
    throttle_scope = "totp_verify"

    def post(self, request):
        serializer = TOTPSetupConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = decode_temp_token(serializer.validated_data["temp_token"], expected_purpose="totp_setup")
        if not user:
            return Response({"detail": "Sessiya bitib, yenidən daxil olun."}, status=401)

        if not user.verify_totp(serializer.validated_data["code"]):
            log_security_event("TOTP_SETUP_FAILED", user=user, ip=get_client_ip(request))
            return Response({"detail": "Kod yanlışdır."}, status=400)

        user.totp_confirmed = True
        user.save(update_fields=["totp_confirmed"])

        log_security_event("TOTP_SETUP_COMPLETE", user=user, ip=get_client_ip(request))

        # İlk giriş: admin tərəfindən yaradılan istifadəçi 2FA-nı təsdiqlədi - indi öz yeni
        # şifrəsini təyin etməlidir (bax FirstLoginPasswordSetView). Adətən bu vəziyyət yalnız
        # yeni yaradılmış istifadəçilərdə olur (must_change_password admin tərəfindən sıfırlanmış
        # 2FA-dan sonra deyil, yalnız yaradılışda True olur).
        if user.must_change_password:
            temp_token = issue_short_lived_token(user, purpose="password_change")
            return Response({
                "step": "password_change_required",
                "temp_token": temp_token,
            })

        access, refresh = issue_jwt_pair(user)
        return Response({
            "step": "done",
            "access": access,
            "refresh": refresh,
            "user": UserSerializer(user).data,
        })


class TOTPVerifyView(APIView):
    """Normal giriş axınının 2-ci addımı: authenticator kodunu yoxlayır."""
    permission_classes = [AllowAny]
    throttle_scope = "totp_verify"

    def post(self, request):
        serializer = TOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = decode_temp_token(serializer.validated_data["temp_token"], expected_purpose="totp_verify")
        if not user:
            return Response({"detail": "Sessiya bitib, yenidən daxil olun."}, status=401)

        code = serializer.validated_data["code"]
        ip = get_client_ip(request)

        if not user.verify_totp(code):
            log_security_event("TOTP_VERIFY_FAILED", user=user, ip=ip)
            return Response({"detail": "Kod yanlışdır."}, status=401)

        log_security_event("LOGIN_SUCCESS", user=user, ip=ip)
        access, refresh = issue_jwt_pair(user)
        return Response({"access": access, "refresh": refresh, "user": UserSerializer(user).data})


GENERIC_TOTP_ADMIN_HELP_RESPONSE = {
    "detail": "Tələbiniz qəbul edildi. Administratorlarınız məlumatlandırıldı."
}


class TOTPRequestAdminHelpView(APIView):
    """
    İstifadəçi 2FA cihazını itirdikdə (bax: AdminResetTOTPView qeydi - self-service bərpa
    YOXDUR) bu endpoint vasitəsilə öz təşkilatının admini/sistem adminlərinə "2FA-nı sıfırla"
    tələbi göndərə bilər. Girişsiz (temp_token/JWT olmadan) çağırılır, ona görə forgot-password
    axını kimi həmişə eyni (generic) cavab qaytarır - istifadəçinin mövcudluğunu sızdırmır.
    """
    permission_classes = [AllowAny]
    throttle_scope = "forgot_password"

    def post(self, request):
        serializer = TOTPRequestAdminHelpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        message = serializer.validated_data["message"]
        ip = get_client_ip(request)

        user = User.objects.filter(username=username, is_active=True).first()
        if user:
            admins = User.objects.filter(
                Q(is_staff=True) | Q(is_org_admin=True, organization=user.organization),
                is_active=True,
            ).exclude(id=user.id).exclude(email="")

            body_lines = [
                f"İstifadəçi {user.username} ({user.first_name} {user.last_name}) "
                f"2FA (autentifikator) üçün admin köməyi tələb edir.",
                "2FA-nı sıfırlamaq üçün İnzibatçı Panelindən istifadə edin.",
            ]
            if message:
                body_lines.append(f"İstifadəçinin mesajı: {message}")

            for admin in admins:
                send_mail_to(admin.email, "2FA üçün admin köməyi tələbi", "\n".join(body_lines))

            log_security_event("TOTP_ADMIN_HELP_REQUESTED", user=user, ip=ip)
        else:
            log_security_event("TOTP_ADMIN_HELP_REQUESTED_INVALID", ip=ip, extra=f"username={username}")

        return Response(GENERIC_TOTP_ADMIN_HELP_RESPONSE)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
        except Exception:
            pass
        log_security_event("LOGOUT", user=request.user, ip=get_client_ip(request))
        return Response(status=204)


class ForgotPasswordRequestView(APIView):
    """
    1-ci addim: istifadəçi adı VƏ YA e-poçt. Tapilarsa qeydiyyatdaki e-poctuna kod gonderilir.
    Hech bir halda (istifadeci yoxdur / bloklanib / basqa xeta) fergli cavab qaytarilmir -
    ancaq bloklanmis hesaba kod gonderilmir (lockout bypass qarsisi).
    """
    permission_classes = [AllowAny]
    throttle_scope = "forgot_password"

    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        ip = get_client_ip(request)

        user = User.objects.filter(
            Q(username=identifier) | Q(email__iexact=identifier), is_active=True
        ).first()
        if user and not user.is_locked:
            code = generate_numeric_code(6)
            PasswordResetCode.objects.create(
                user=user,
                code_hash=hash_code(code),
                expires_at=timezone.now() + timezone.timedelta(
                    minutes=settings.PASSWORD_RESET_CODE_TTL_MINUTES
                ),
                requested_ip=ip,
            )
            send_mail_to(
                user.email,
                "Şifrə bərpası",
                f"Şifrənizi bərpa etmək üçün kod: {code}\n"
                f"Kod {settings.PASSWORD_RESET_CODE_TTL_MINUTES} dəqiqə etibarlıdır.\n"
                f"Bu tələbi siz etməmisinizsə, bu mesajı gözardı edin.",
            )
            log_security_event("PASSWORD_RESET_REQUESTED", user=user, ip=ip)
        else:
            log_security_event("PASSWORD_RESET_REQUESTED_INVALID", ip=ip, extra=f"identifier={identifier}")

        return Response(GENERIC_FORGOT_PASSWORD_RESPONSE)


class ForgotPasswordConfirmView(APIView):
    """2-ci addim: istifadəçi adı/e-poçt + e-poçta gələn kod + yeni şifrə."""
    permission_classes = [AllowAny]
    throttle_scope = "forgot_password"

    def post(self, request):
        serializer = ForgotPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = get_client_ip(request)

        user = User.objects.filter(
            Q(username=data["identifier"]) | Q(email__iexact=data["identifier"])
        ).first()
        if not user:
            return Response({"detail": "Kod yanlış və ya vaxtı bitib."}, status=400)

        reset = (
            PasswordResetCode.objects.filter(user=user, used=False)
            .order_by("-created_at")
            .first()
        )
        if not reset or not reset.is_valid() or reset.code_hash != hash_code(data["code"]):
            log_security_event("PASSWORD_RESET_CODE_INVALID", user=user, ip=ip)
            return Response({"detail": "Kod yanlış və ya vaxtı bitib."}, status=400)

        user.set_password(data["new_password"])
        user.failed_login_attempts = 0
        # Admin tərəfindən yaradılan istifadəçi ilk şifrəsini məhz bu (e-poçta gələn kod) axını
        # ilə təyin edir - buna görə must_change_password də burada təmizlənməlidir, əks halda
        # istifadəçi yeni şifrəsi ilə daxil olanda YENƏ "yeni şifrə təyin et" ekranına düşür.
        user.must_change_password = False
        user.save(update_fields=["password", "failed_login_attempts", "must_change_password"])
        reset.used = True
        reset.save(update_fields=["used"])

        log_security_event("PASSWORD_RESET_SUCCESS", user=user, ip=ip)
        send_mail_to(
            user.email, "Şifrəniz dəyişdirildi",
            "Hesabınızın şifrəsi uğurla dəyişdirildi. Bu siz deyildinizsə, dərhal administrator ilə əlaqə saxlayın.",
        )
        return Response({"detail": "Şifrə uğurla dəyişdirildi. İndi yenidən daxil ola bilərsiniz."})


class ChangePasswordView(APIView):
    """Daxil olmuş istifadəçi öz şifrəsini dəyişir (profil səhifəsindən)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Cari şifrə yanlışdır."}, status=400)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        log_security_event("PASSWORD_CHANGED", user=user, ip=get_client_ip(request))
        return Response({"detail": "Şifrə dəyişdirildi."})


class MeView(APIView):
    """Şəxsi kabinet (Image 4). GET - öz məlumatları, PATCH - öz məlumatlarını redaktə et."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = SelfProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_security_event("PROFILE_SELF_UPDATE", user=request.user, ip=get_client_ip(request))
        return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Admin-only: istifadəçi yaratma, kilidi açma, 2FA sıfırlama
# ---------------------------------------------------------------------------

DEFAULT_INITIAL_PASSWORD = "AA123456!"


class CreateUserView(APIView):
    """Image 3-dəki 'Yeni istifadəçi' formu. Yalnız admin/idarəçi çağıra bilər.

    Dizaynda şifrə sahəsi yoxdur -> şifrə göndərilməzsə HAMISI ÜÇÜN sabit ilkin şifrə
    (DEFAULT_INITIAL_PASSWORD) təyin olunur. Kod/e-poçt YOXDUR - admin bu sabit şifrəni
    istifadəçiyə özü bildirir. İstifadəçi bu şifrə ilə daxil olanda (must_change_password=True
    olduğu üçün) avtomatik, kodsuz "yeni şifrə təyin et" ekranına yönləndirilir
    (bax LoginView -> _next_login_step_response).
    'İcazə veriləcək modullar' + 'Status' (Baxış/Redaktə/Təsdiq) seçimləri varsa,
    UserModulePermission qeydləri də bu zaman yaradılır.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from permissions_module.models import Module, UserModulePermission

        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        modules_data = data.pop("modules", []) or []
        password = data.pop("password", "") or DEFAULT_INITIAL_PASSWORD

        user = User(**data)
        user.set_password(password)
        # Bütün istifadəçiləri admin yaradır - ilk girişdə kodsuz, birbaşa yeni şifrə təyin etməyə yönləndirilir.
        user.must_change_password = True
        user.save()

        for item in modules_data:
            module = Module.objects.filter(id=item.get("module")).first()
            if not module:
                continue
            UserModulePermission.objects.update_or_create(
                user=user, module=module,
                defaults={
                    "can_view": bool(item.get("can_view", False)),
                    "can_edit": bool(item.get("can_edit", False)),
                    "can_approve": bool(item.get("can_approve", False)),
                    "granted_by": request.user,
                },
            )

        log_security_event("USER_CREATED", user=request.user, ip=get_client_ip(request),
                            extra=f"created_user={user.username}")
        return Response(UserListSerializer(user).data, status=201)


class UserListView(generics.ListAPIView):
    """İnzibatçı Paneli -> İstifadəçilər siyahısı (Image 2).

    Staff/superuser bütün istifadəçiləri görür. Qurum admini (is_org_admin=True) yalnız öz
    təşkilatı (+ alt-təşkilatları) daxilindəki istifadəçiləri görür."""
    permission_classes = [IsStaffOrOrgAdmin]
    serializer_class = UserListSerializer

    def get_queryset(self):
        qs = User.objects.select_related("organization").order_by("first_name", "last_name", "username")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
        organization_id = self.request.query_params.get("organization")
        search = self.request.query_params.get("search")
        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(email__icontains=search) | Q(username__icontains=search)
            )
        return qs


class UserAdminDetailView(generics.RetrieveUpdateAPIView):
    """İnzibatçı Paneli -> İstifadəçi redaktəsi və status (Aktiv/Deaktiv) dəyişimi (Image 2).

    Qurum admini yalnız öz təşkilatındakı (+ alt-təşkilatlar) istifadəçilərə çata bilir (əhatədən
    kənar id üçün 404 qayıdır) və onları redaktə edə bilir, lakin 'organization' və 'is_org_admin'
    sahələrini dəyişə bilmir - bunları yalnız staff/superuser dəyişə bilər (aşağıdakı perform_update)."""
    permission_classes = [IsStaffOrOrgAdmin]

    def get_queryset(self):
        qs = User.objects.select_related("organization")
        org_ids = scoped_organization_ids(self.request.user)
        if org_ids is not None:
            qs = qs.filter(organization_id__in=org_ids)
        return qs

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserAdminUpdateSerializer
        return UserListSerializer

    def perform_update(self, serializer):
        if not is_full_admin(self.request.user):
            serializer.validated_data.pop("organization", None)
            serializer.validated_data.pop("is_org_admin", None)
        user = serializer.save()
        log_security_event(
            "ADMIN_USER_UPDATED", user=self.request.user, ip=get_client_ip(self.request),
            extra=f"target={user.username} is_active={user.is_active}",
        )


class AdminUnlockUserView(APIView):
    """Bloklanmış istifadəçinin kilidini administrator açır."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = UnlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = User.objects.get(id=serializer.validated_data["user_id"])
        except User.DoesNotExist:
            return Response({"detail": "İstifadəçi tapılmadı."}, status=404)

        target.is_locked = False
        target.locked_at = None
        target.failed_login_attempts = 0
        target.save(update_fields=["is_locked", "locked_at", "failed_login_attempts"])

        log_security_event("ADMIN_UNLOCK_USER", user=request.user, ip=get_client_ip(request),
                            extra=f"target={target.username}")
        send_mail_to(target.email, "Hesabınız aktivləşdirildi",
                     "Hesabınızın bloku administrator tərəfindən aradan qaldırıldı.")
        return Response({"detail": "İstifadəçinin kilidi açıldı."})


class AdminResetTOTPView(APIView):
    """
    Istifadeci 2FA cihazini itirdikde - self-service bərpa YOXDUR (təhlükəsizlik üçün),
    yalnız administrator sıfırlaya bilər. Növbəti girişdə istifadəçi yenidən QR quracaq.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminResetTOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = User.objects.get(id=serializer.validated_data["user_id"])
        except User.DoesNotExist:
            return Response({"detail": "İstifadəçi tapılmadı."}, status=404)

        target.reset_totp()
        log_security_event("ADMIN_RESET_TOTP", user=request.user, ip=get_client_ip(request),
                            extra=f"target={target.username}")
        send_mail_to(target.email, "2FA sıfırlandı",
                     "İki mərhələli doğrulama (2FA) parametrləriniz administrator tərəfindən "
                     "sıfırlandı. Növbəti daxil olduğunuzda yenidən quracaqsınız.")
        return Response({"detail": "2FA sıfırlandı."})


def secrets_token() -> str:
    import secrets
    return secrets.token_hex(4)