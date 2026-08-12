import hashlib
import logging
import secrets

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

security_logger = logging.getLogger("security")

TEMP_TOKEN_SALT = "authentication.temp_token.v1"


def issue_short_lived_token(user, purpose: str) -> str:
    """
    Login -> 2FA arasindaki (ve TOTP setup) qisa omurlu, meqsedi qeydli token.
    JWT deyil - hele tam autentifikasiya olunmadigi ucun sadece signed payload kifayetdir.
    """
    payload = {"uid": user.id, "purpose": purpose}
    return signing.dumps(payload, salt=TEMP_TOKEN_SALT)


def decode_temp_token(token: str, expected_purpose: str):
    from .models import User

    if not token:
        return None
    try:
        data = signing.loads(
            token, salt=TEMP_TOKEN_SALT, max_age=settings.TEMP_TOKEN_TTL_SECONDS
        )
    except signing.BadSignature:
        return None
    if data.get("purpose") != expected_purpose:
        return None
    try:
        return User.objects.get(id=data["uid"])
    except User.DoesNotExist:
        return None


def issue_jwt_pair(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def generate_numeric_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def send_mail_to(to_email: str, subject: str, body: str) -> None:
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    except Exception:
        security_logger.exception("Email gonderilmesi ugursuz oldu: %s", to_email)


def log_security_event(event: str, *, user=None, ip: str = "", extra: str = "") -> None:
    security_logger.info(
        "event=%s user=%s ip=%s %s",
        event, getattr(user, "username", "-"), ip, extra,
    )
    try:
        from audit.models import AuditLog
        AuditLog.objects.create(user=user, action=event, ip_address=ip or None, detail=extra)
    except Exception:
        # Audit DB yazisi ugursuz olsa da autentifikasiya axini kesilmemelidir,
        # amma bu HEC vaxt sessiz olmamalidir - console logu yenede yazilib yuxarida.
        security_logger.exception("AuditLog yazisi ugursuz oldu: event=%s", event)
