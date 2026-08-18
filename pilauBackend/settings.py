"""
Django settings - maksimum tehlukesizlik konfiqurasiyasi ile.
"""
from datetime import timedelta
from pathlib import Path

from decouple import Config, Csv, RepositoryEnv,config
from tutorial.settings import ALLOWED_HOSTS

BASE_DIR = Path(__file__).resolve().parent.parent

# python-decouple-in defolt config() funksiyasi .env-i CWD-den (serveri hardan ise
# saldiginizdan) axtarir - bu, IDE/terminal-dan asili olaraq tapilmamasina sebeb olur.
# Ona gore .env-i HEMISE BASE_DIR-e (manage.py-in yaninda) gore, cwd-den asili olmadan oxuyuruq.
_env_path = BASE_DIR / ".env"
if not _env_path.exists():
    raise RuntimeError(
        f".env faylı tapılmadı: {_env_path}\n"
        f".env.example-i kopyalayıb '{BASE_DIR}' qovluğunda (manage.py ilə eyni yerdə) "
        f".env adı ilə saxlayın: cp .env.example .env"
    )
config = Config(RepositoryEnv(str(_env_path)))

# --------------------------------------------------------------------------
# Esas
# --------------------------------------------------------------------------
DJANGO_ENV = config("DJANGO_ENV", default="development")
DEBUG = config("DEBUG", default=False, cast=bool)
SECRET_KEY = config("SECRET_KEY")
# ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
ALLOWED_HOSTS=['*']
AUTH_USER_MODEL = "authentication.User"

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    "authentication",
    "organizations",
    "permissions_module",
    "audit",
    "licenses",
    "workflow",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "audit.middleware.RequestAuditMiddleware",
]

ROOT_URLCONF = "pilauBackend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pilauBackend.wsgi.application"

# --------------------------------------------------------------------------
# DB - production-da Postgres, lokal deveetlopment-de sqlite
# --------------------------------------------------------------------------
if DJANGO_ENV == "production":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --------------------------------------------------------------------------
# Sifre siyaseti - Argon2 + guclu validatorlar
# --------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "authentication.validators.ComplexityValidator"},
]

# --------------------------------------------------------------------------
# DRF + JWT (qisa omurlu access, rotate + blacklist edilen refresh)
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "totp_verify": "10/min",
        "forgot_password": "5/min",
    },
    # "EXCEPTION_HANDLER": "pilauBackend.exception_handlers.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------
# 2FA / temp-token / lockout sabitleri
# --------------------------------------------------------------------------
TOTP_ENCRYPTION_KEY = config("TOTP_ENCRYPTION_KEY").encode()

# Erken (server basladiqda) yoxlama - yanlish/placeholder acar qalsa, ilk request-de deyil,
# serveri qaldiranda aydin xeta versin. Novbeti '2fa-nı yükləyə bilmədi' kimi qeyri-müəyyən
# xetalarin qarsisini alir.
try:
    from cryptography.fernet import Fernet as _FernetCheck
    _FernetCheck(TOTP_ENCRYPTION_KEY)
except Exception as _e:
    raise RuntimeError(
        "TOTP_ENCRYPTION_KEY .env faylinda duzgun deyil (placeholder qalib ve ya sehv formatdadir). "
        "Duzgun acar generasiya etmek ucun: "
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
        "ve neticeni .env-de TOTP_ENCRYPTION_KEY= olaraq yazin."
    ) from _e

TEMP_TOKEN_TTL_SECONDS = 300          # login -> 2FA arasindaki muveqqeti token omru
MAX_FAILED_LOGIN_ATTEMPTS = 3         # 3-cu sehvden sonra bloklanir
PASSWORD_RESET_CODE_TTL_MINUTES = 10
ADMIN_CONTACT_EMAIL = config("ADMIN_CONTACT_EMAIL", default="")
ADMIN_CONTACT_PHONE = config("ADMIN_CONTACT_PHONE", default="")

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST \
    else "django.core.mail.backends.console.EmailBackend"
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=(EMAIL_PORT != 465), cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=(EMAIL_PORT == 465), cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "noreply@example.gov.az")

# --------------------------------------------------------------------------
# CORS - yalnix frontend origin-e icaze
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [config("FRONTEND_ORIGIN", default="http://localhost:3000")]
CORS_ALLOW_CREDENTIALS = True

# --------------------------------------------------------------------------
# Cookie / CSRF / Session tehlukesizliyi
# --------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = False  # frontend JS-in CSRF tokenini oxuya bilmesi ucun False qalmalidir
CSRF_COOKIE_SAMESITE = "Strict"

if DJANGO_ENV == "production":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"

# --------------------------------------------------------------------------
# Beynelxalqlashdirma
# --------------------------------------------------------------------------
LANGUAGE_CODE = "az"
TIME_ZONE = "Asia/Baku"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Fayl yükləmə həddi (icazə sənədi faylları üçün) - field_schema.py-dəki max_size_mb ilə uyğun
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# --------------------------------------------------------------------------
# Jazzmin - admin panel görünüşü
# --------------------------------------------------------------------------
JAZZMIN_SETTINGS = {
    "site_title": "MSN İnzibatçı Paneli",
    "site_header": "MSN İdarəetmə",
    "site_brand": "MSN Admin",
    "welcome_sign": "MSN İnzibatçı panelinə xoş gəldiniz",
    "copyright": "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi",
    "search_model": ["authentication.User", "organizations.Organization", "permissions_module.Module"],
    "user_avatar": None,

    "topmenu_links": [
        {"name": "Sayt", "url": "/", "new_window": True},
        {"model": "authentication.User"},
        {"app": "permissions_module"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "authentication", "organizations", "permissions_module", "audit",
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "authentication.User": "fas fa-user",
        "authentication.PasswordResetCode": "fas fa-key",
        "organizations.Organization": "fas fa-building",
        "organizations.AuthorizedPerson": "fas fa-id-badge",
        "permissions_module.Module": "fas fa-sitemap",
        "permissions_module.UserModulePermission": "fas fa-user-shield",
        "audit.AuditLog": "fas fa-history",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "authentication.User": "collapsible",
        "permissions_module.Module": "collapsible",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-navy",
    "accent": "accent-navy",
    "navbar": "navbar-navy navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-navy",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-navy",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# --------------------------------------------------------------------------
# Logging - butun autentifikasiya hadiseleri console/fayla yazilir
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name} - {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        "security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}