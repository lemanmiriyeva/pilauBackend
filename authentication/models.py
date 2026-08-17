import hashlib

import pyotp
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


def _fernet():
    return Fernet(settings.TOTP_ENCRYPTION_KEY)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField("Telefon", max_length=20, blank=True)
    fin_kod = models.CharField("FIN kod", max_length=10, blank=True)
    id_card_serial = models.CharField("Şəxsiyyət vəsiqəsinin seriya nömrəsi", max_length=20, blank=True)
    # QEYD: bu iki sahə serializers.py-də (UserSerializer, SelfProfileUpdateSerializer və s.)
    # artıq istifadə olunurdu, amma modeldə yox idi - bu, /api/auth/me/ və bir çox istifadəçi
    # endpoint-ini "field department is not defined on model" xətası ilə sındırırdı. Bərpa edildi.
    department = models.CharField("Departament/Şöbə", max_length=255, blank=True)
    position = models.CharField("Vəzifə", max_length=255, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="users",
    )
    # Qurum admini: is_staff (MSN inzibatçısı) olmadan, yalnız öz təşkilatı (+ alt-təşkilatları)
    # daxilində - Lisenziya/icazə sənədləri, Təşkilatlar və İstifadəçilər modullarında - tam
    # görünürlük və redaktə icazəsi verir. Bax: organizations/permissions.py, licenses/views.py,
    # authentication/views.py (UserListView, UserAdminDetailView).
    is_org_admin = models.BooleanField("Qurum admini", default=False)

    # --- İlk giriş - admin tərəfindən yaradılan hər istifadəçi ilk dəfə daxil olduqda
    # şifrəni özü təyin etməlidir (kodsuz, birbaşa) ---
    must_change_password = models.BooleanField("Şifrəni dəyişməlidir (ilk giriş)", default=False)

    # --- Lockout ---
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    # --- 2FA (TOTP - Google Authenticator uyumlu) ---
    totp_secret_encrypted = models.BinaryField(null=True, blank=True)
    totp_confirmed = models.BooleanField(default=False)
    totp_backup_codes = models.JSONField(default=list, blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "İstifadəçi"
        verbose_name_plural = "İstifadəçilər"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})".strip()

    # ---- TOTP helpers ----
    def set_totp_secret(self, secret: str) -> None:
        self.totp_secret_encrypted = _fernet().encrypt(secret.encode())

    def get_totp_secret(self) -> str:
        return _fernet().decrypt(bytes(self.totp_secret_encrypted)).decode()

    def verify_totp(self, code: str) -> bool:
        if not self.totp_secret_encrypted or not code:
            return False
        totp = pyotp.TOTP(self.get_totp_secret())
        return totp.verify(code, valid_window=1)

    def consume_backup_code(self, code: str) -> bool:
        if not code or not self.totp_backup_codes:
            return False
        code_hash = hashlib.sha256(code.strip().encode()).hexdigest()
        if code_hash in self.totp_backup_codes:
            self.totp_backup_codes = [c for c in self.totp_backup_codes if c != code_hash]
            self.save(update_fields=["totp_backup_codes"])
            return True
        return False

    def register_failed_login(self) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            self.is_locked = True
            from django.utils import timezone
            self.locked_at = timezone.now()
        self.save(update_fields=["failed_login_attempts", "is_locked", "locked_at"])

    def reset_failed_login(self) -> None:
        if self.failed_login_attempts or self.is_locked:
            self.failed_login_attempts = 0
            self.save(update_fields=["failed_login_attempts"])

    def reset_totp(self) -> None:
        self.totp_secret_encrypted = None
        self.totp_confirmed = False
        self.totp_backup_codes = []
        self.save(update_fields=["totp_secret_encrypted", "totp_confirmed", "totp_backup_codes"])


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_codes")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Şifrə bərpa kodu"
        verbose_name_plural = "Şifrə bərpa kodları"

    def is_valid(self) -> bool:
        from django.utils import timezone
        return not self.used and self.expires_at > timezone.now()