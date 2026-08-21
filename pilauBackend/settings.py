"""
Django settings - maksimum tehlukesizlik konfiqurasiyasi ile.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Config, Csv, RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================================================
# .ENV
# ==========================================================================

_env_path = BASE_DIR / ".env"

if not _env_path.exists():
    raise RuntimeError(
        f".env faylı tapılmadı: {_env_path}\n"
        f".env.example-i kopyalayıb '{BASE_DIR}' qovluğunda "
        f"(manage.py ilə eyni yerdə) .env adı ilə saxlayın."
    )

config = Config(RepositoryEnv(str(_env_path)))

# ==========================================================================
# ƏSAS
# ==========================================================================

DJANGO_ENV = config(
    "DJANGO_ENV",
    default="development"
)

DEBUG = config(
    "DEBUG",
    default=False,
    cast=bool
)

SECRET_KEY = config("SECRET_KEY")

# Server daxili IP ilə işlədiyi üçün
ALLOWED_HOSTS = [
    "*",
]

AUTH_USER_MODEL = "authentication.User"

# ==========================================================================
# INSTALLED APPS
# ==========================================================================

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

# ==========================================================================
# MIDDLEWARE
# ==========================================================================

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

# ==========================================================================
# URL / TEMPLATES
# ==========================================================================

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

# ==========================================================================
# DATABASE
# ==========================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ==========================================================================
# PASSWORD
# ==========================================================================

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator",

        "OPTIONS": {
            "min_length": 10
        },
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
    },

    {
        "NAME":
            "authentication.validators.ComplexityValidator"
    },
]

# ==========================================================================
# DJANGO REST FRAMEWORK
# ==========================================================================

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
}

# ==========================================================================
# JWT
# ==========================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),

    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),

    "ROTATE_REFRESH_TOKENS": True,

    "BLACKLIST_AFTER_ROTATION": True,

    "UPDATE_LAST_LOGIN": True,

    "ALGORITHM": "HS256",

    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),
}

# ==========================================================================
# 2FA
# ==========================================================================

TOTP_ENCRYPTION_KEY = config(
    "TOTP_ENCRYPTION_KEY"
).encode()

try:
    from cryptography.fernet import Fernet as _FernetCheck

    _FernetCheck(TOTP_ENCRYPTION_KEY)

except Exception as _e:

    raise RuntimeError(
        "TOTP_ENCRYPTION_KEY .env faylinda duzgun deyil "
        "(placeholder qalib ve ya sehv formatdadir). "
        "Duzgun acar generasiya etmek ucun: "
        "python -c "
        "\"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\""
    ) from _e

TEMP_TOKEN_TTL_SECONDS = 300

MAX_FAILED_LOGIN_ATTEMPTS = 3

PASSWORD_RESET_CODE_TTL_MINUTES = 10

ADMIN_CONTACT_EMAIL = config(
    "ADMIN_CONTACT_EMAIL",
    default=""
)

ADMIN_CONTACT_PHONE = config(
    "ADMIN_CONTACT_PHONE",
    default=""
)

# ==========================================================================
# EMAIL
# ==========================================================================

EMAIL_HOST = config(
    "EMAIL_HOST",
    default=""
)

if EMAIL_HOST:
    EMAIL_BACKEND = (
        "django.core.mail.backends.smtp.EmailBackend"
    )
else:
    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
    )

EMAIL_PORT = config(
    "EMAIL_PORT",
    default=587,
    cast=int
)

EMAIL_USE_TLS = config(
    "EMAIL_USE_TLS",
    default=(EMAIL_PORT != 465),
    cast=bool
)

EMAIL_USE_SSL = config(
    "EMAIL_USE_SSL",
    default=(EMAIL_PORT == 465),
    cast=bool
)

EMAIL_HOST_USER = config(
    "EMAIL_HOST_USER",
    default=""
)

EMAIL_HOST_PASSWORD = config(
    "EMAIL_HOST_PASSWORD",
    default=""
)

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=EMAIL_HOST_USER or "noreply@example.gov.az"
)

# ==========================================================================
# CORS
# ==========================================================================

FRONTEND_ORIGIN = config(
    "FRONTEND_ORIGIN",
    default="http://localhost:3000"
)

CORS_ALLOWED_ORIGINS = [
    FRONTEND_ORIGIN,
]

CORS_ALLOW_CREDENTIALS = True

# ==========================================================================
# CSRF
# ==========================================================================

# Əsas problem burada idi.
#
# Admin:
# http://192.168.1.200/admin/
#
# üçün Django bu origin-i etibarlı CSRF origin kimi tanımalıdır.

CSRF_TRUSTED_ORIGINS = [
    "http://192.168.1.200",
    FRONTEND_ORIGIN,
]

# ==========================================================================
# SESSION / CSRF COOKIE
# ==========================================================================

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Strict"

# Frontend JS CSRF tokenini oxuya bilsin deyə False
CSRF_COOKIE_HTTPONLY = False

CSRF_COOKIE_SAMESITE = "Strict"

# ==========================================================================
# HTTPS / SECURITY
# ==========================================================================

SECURE_SSL_REDIRECT = config(
    "SECURE_SSL_REDIRECT",
    default=False,
    cast=bool
)

# Əgər Nginx HTTPS proxy kimi işləyirsə istifadə olunur.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https"
)

# ==========================================================================
# PRODUCTION SECURITY
# ==========================================================================

if DJANGO_ENV == "production":
    # Əgər serverə HTTP ilə:
    #
    # http://192.168.1.200
    #
    # daxil olursansa, bunlar False qalmalıdır.
    #
    # HTTPS tam qurulduqdan sonra True etmək olar.

    SESSION_COOKIE_SECURE = False

    CSRF_COOKIE_SECURE = False

    SECURE_HSTS_SECONDS = 0

    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

    SECURE_HSTS_PRELOAD = False

    SECURE_CONTENT_TYPE_NOSNIFF = True

    SECURE_BROWSER_XSS_FILTER = True

    X_FRAME_OPTIONS = "DENY"

    SECURE_REFERRER_POLICY = "same-origin"

# ==========================================================================
# INTERNATIONALIZATION
# ==========================================================================

LANGUAGE_CODE = "az"

TIME_ZONE = "Asia/Baku"

USE_I18N = True

USE_TZ = True

# ==========================================================================
# STATIC / MEDIA
# ==========================================================================

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"

MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==========================================================================
# FILE UPLOAD
# ==========================================================================

DATA_UPLOAD_MAX_MEMORY_SIZE = (
        20 * 1024 * 1024
)

# ==========================================================================
# JAZZMIN
# ==========================================================================

JAZZMIN_SETTINGS = {

    "site_title":
        "MSN İnzibatçı Paneli",

    "site_header":
        "MSN İdarəetmə",

    "site_brand":
        "MSN Admin",

    "welcome_sign":
        "MSN İnzibatçı panelinə xoş gəldiniz",

    "copyright":
        "Azərbaycan Respublikasının Müdafiə Sənayesi Nazirliyi",

    "search_model": [
        "authentication.User",
        "organizations.Organization",
        "permissions_module.Module",
    ],

    "user_avatar": None,

    "topmenu_links": [
        {
            "name": "Sayt",
            "url": "/",
            "new_window": True
        },

        {
            "model":
                "authentication.User"
        },

        {
            "app":
                "permissions_module"
        },
    ],

    "show_sidebar": True,

    "navigation_expanded": True,

    "hide_apps": [],

    "hide_models": [],

    "order_with_respect_to": [
        "authentication",
        "organizations",
        "permissions_module",
        "audit",
    ],

    "icons": {

        "auth":
            "fas fa-users-cog",

        "authentication.User":
            "fas fa-user",

        "authentication.PasswordResetCode":
            "fas fa-key",

        "organizations.Organization":
            "fas fa-building",

        "organizations.AuthorizedPerson":
            "fas fa-id-badge",

        "permissions_module.Module":
            "fas fa-sitemap",

        "permissions_module.UserModulePermission":
            "fas fa-user-shield",

        "audit.AuditLog":
            "fas fa-history",
    },

    "default_icon_parents":
        "fas fa-chevron-circle-right",

    "default_icon_children":
        "fas fa-circle",

    "related_modal_active":
        True,

    "custom_css":
        None,

    "custom_js":
        None,

    "use_google_fonts_cdn":
        True,

    "show_ui_builder":
        False,

    "changeform_format":
        "horizontal_tabs",

    "changeform_format_overrides": {

        "authentication.User":
            "collapsible",

        "permissions_module.Module":
            "collapsible",
    },
}

# ==========================================================================
# JAZZMIN UI
# ==========================================================================

JAZZMIN_UI_TWEAKS = {

    "navbar_small_text":
        False,

    "footer_small_text":
        False,

    "body_small_text":
        False,

    "brand_small_text":
        False,

    "brand_colour":
        "navbar-navy",

    "accent":
        "accent-navy",

    "navbar":
        "navbar-navy navbar-dark",

    "no_navbar_border":
        False,

    "navbar_fixed":
        True,

    "layout_boxed":
        False,

    "footer_fixed":
        False,

    "sidebar_fixed":
        True,

    "sidebar":
        "sidebar-dark-navy",

    "sidebar_nav_small_text":
        False,

    "sidebar_disable_expand":
        False,

    "sidebar_nav_child_indent":
        True,

    "sidebar_nav_compact_style":
        False,

    "sidebar_nav_legacy_style":
        False,

    "sidebar_nav_flat_style":
        False,

    "theme":
        "default",

    "dark_mode_theme":
        None,

    "button_classes": {

        "primary":
            "btn-navy",

        "secondary":
            "btn-secondary",

        "info":
            "btn-info",

        "warning":
            "btn-warning",

        "danger":
            "btn-danger",

        "success":
            "btn-success",
    },
}

# ==========================================================================
# LOGGING
# ==========================================================================

LOGGING = {

    "version": 1,

    "disable_existing_loggers":
        False,

    "formatters": {

        "verbose": {
            "format":
                "[{asctime}] {levelname} {name} - {message}",
            "style": "{",
        },
    },

    "handlers": {

        "console": {
            "class":
                "logging.StreamHandler",

            "formatter":
                "verbose",
        },
    },

    "loggers": {

        "security": {

            "handlers": [
                "console"
            ],

            "level":
                "INFO",

            "propagate":
                False,
        },

        "django": {

            "handlers": [
                "console"
            ],

            "level":
                "WARNING",

            "propagate":
                False,
        },
    },
}
