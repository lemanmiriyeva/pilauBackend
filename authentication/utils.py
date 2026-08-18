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


def send_mail_to(
    to_email: str, subject: str, body: str, *,
    eyebrow: str | None = None,
    code: str | None = None,
    ttl_minutes: int | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
    not_you_hint: str | None = None,
) -> None:
    """Sistemdəki BÜTÜN mail göndərmələri bu funksiyadan keçir - vahid, brendlənmiş bildiriş
    kartı dizaynı üçün (bax templates/emails/base_email.html). Köhnə çağırışlar
    (yalnız to_email, subject, body) dəyişmədən işləməyə davam edir; yeni parametrlər
    (code, cta_url və s.) optional-dır və şablonu zənginləşdirir."""
    if not settings.EMAIL_HOST:
        # .env-də EMAIL_HOST doldurulmayıb - kod/mail console-a (server loguna) yazılır,
        # real mail GETMƏYƏCƏK. Bu, "mail gəlmir" şikayətinin ən çox rast gəlinən səbəbidir.
        security_logger.warning(
            "EMAIL_HOST bos oldugu ucun mail console backend ile 'gonderilir' (real mail YOXDUR): to=%s subject=%s",
            to_email, subject,
        )

    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    absolute_cta_url = None
    if cta_url:
        frontend_base = getattr(settings, "FRONTEND_BASE_URL", "")
        absolute_cta_url = cta_url if cta_url.startswith("http") else f"{frontend_base}{cta_url}"

    html_body = render_to_string("emails/base_email.html", {
        "subject": subject,
        "eyebrow": eyebrow,
        "title": subject,
        "body": body,
        "code": code,
        "ttl_minutes": ttl_minutes or getattr(settings, "PASSWORD_RESET_CODE_TTL_MINUTES", 10),
        "cta_text": cta_text,
        "cta_url": absolute_cta_url,
        "not_you_hint": not_you_hint,
    })

    # Mətn versiyası - HTML dəstəkləməyən klientlər üçün fallback.
    text_lines = [body]
    if code:
        text_lines.append(f"\nKod: {code} ({ttl_minutes or getattr(settings, 'PASSWORD_RESET_CODE_TTL_MINUTES', 10)} dəqiqə etibarlıdır)")
    if absolute_cta_url:
        text_lines.append(f"\n{cta_text or 'Keçid'}: {absolute_cta_url}")
    text_body = "\n".join(text_lines)

    try:
        message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [to_email])
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
    except Exception as exc:
        # QEYD: bu istisna qəsdən udulur ki, mail server-i cavab verməsə/yavaş olsa,
        # istifadəçi axını (məs. sifre bərpası kodu yaradılması) kəsilməsin. Amma səbəbini
        # görmək üçün MÜTLƏQ server logunda (security logger) axtar - ən çox rast gəlinənlər:
        #  - EMAIL_HOST_USER/EMAIL_HOST_PASSWORD səhvdir (Gmail üçün "App password" lazımdır,
        #    adi hesab parolu ilə SMTPAuthenticationError verir)
        #  - EMAIL_PORT/EMAIL_USE_TLS/EMAIL_USE_SSL uyğunsuzdur (587->TLS, 465->SSL)
        #  - Hosting/firewall SMTP portunu (25/587) bağlayıb (bir çox bulud provayderi bunu edir)
        #  - .env faylı deploy zamanı yüklənməyib, EMAIL_HOST boş qalıb (yuxarıdakı warning bunu göstərir)
        security_logger.exception(
            "Email gonderilmesi ugursuz oldu: to=%s host=%s port=%s user=%s error=%s",
            to_email, settings.EMAIL_HOST, settings.EMAIL_PORT, settings.EMAIL_HOST_USER, exc,
        )


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