import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("SONGPICKER_DEV") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "django-insecure-local-songpicker-development-only" if DEBUG else ""
)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "").split(",")
PUBLIC_URL = os.environ.get("SONGPICKER_PUBLIC_URL", "http://localhost:8000" if DEBUG else "").rstrip("/")
PUBLIC_SIGNUP = DEBUG or os.environ.get("SONGPICKER_PUBLIC_SIGNUP") == "1"
PREFLIGHT_SIGNUP_EMAILS = frozenset(
    email.strip().lower()
    for email in os.environ.get("SONGPICKER_PREFLIGHT_EMAILS", "").split(",")
    if email.strip()
)
LEGAL_NOTICE_URL = os.environ.get("SONGPICKER_LEGAL_NOTICE_URL", "")
PRIVACY_NOTICE_URL = os.environ.get("SONGPICKER_PRIVACY_NOTICE_URL", "")
TRUSTED_PROXY_HOPS = int(os.environ.get("SONGPICKER_TRUSTED_PROXY_HOPS", "0"))
if not 0 <= TRUSTED_PROXY_HOPS <= 5:
    raise ImproperlyConfigured("SONGPICKER_TRUSTED_PROXY_HOPS must be between 0 and 5.")

ROOT_URLCONF = "bandapp.urls"
WSGI_APPLICATION = "bandapp.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "bandapp",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bandapp.limits.AccountLimits", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True,
              "OPTIONS": {"context_processors": [
                  "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
                  "django.contrib.messages.context_processors.messages", "bandapp.context.public_settings",
              ]}}]
def database_settings():
    if DEBUG and not os.environ.get("DATABASE_URL"):
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "songpicker.sqlite3"}
    url = urlsplit(os.environ.get("DATABASE_URL", ""))
    if url.scheme in {"postgres", "postgresql"} and url.hostname and url.path.strip("/"):
        db = {"NAME": unquote(url.path[1:]), "USER": unquote(url.username or ""),
              "PASSWORD": unquote(url.password or ""), "HOST": url.hostname, "PORT": url.port or 5432}
    else:
        db = {key: os.environ[f"PG{variable}"] for key, variable in (
            ("NAME", "DATABASE"), ("USER", "USER"), ("PASSWORD", "PASSWORD"), ("HOST", "HOST"),
        )}
        db["PORT"] = os.environ.get("PGPORT", "5432")
    return {"ENGINE": "django.db.backends.postgresql", **db,
            "OPTIONS": {"sslmode": os.environ.get("PGSSLMODE", "require")}}


DATABASES = {"default": database_settings()}
PASSWORD_RESET_TIMEOUT = 60 * 60
DATA_UPLOAD_MAX_MEMORY_SIZE = 256_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_000_000
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{validator}"}
    for validator in ("UserAttributeSimilarityValidator", "MinimumLengthValidator",
                      "CommonPasswordValidator", "NumericPasswordValidator")
]
LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
elif BREVO_API_KEY:
    EMAIL_BACKEND = "bandapp.mail.BrevoEmailBackend"
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("SMTP_FROM", "songpicker@example.invalid" if DEBUG else "")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
if os.environ.get("TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    if not (SECRET_KEY and PUBLIC_URL.startswith("https://") and (BREVO_API_KEY or EMAIL_HOST) and DEFAULT_FROM_EMAIL):
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY, HTTPS SONGPICKER_PUBLIC_URL, BREVO_API_KEY or SMTP_HOST, and SMTP_FROM.")

    if PUBLIC_SIGNUP and not all(
        urlsplit(url).scheme == "https" and urlsplit(url).hostname
        for url in (LEGAL_NOTICE_URL, PRIVACY_NOTICE_URL)
    ):
        raise ImproperlyConfigured("Public signup requires HTTPS legal and privacy notice URLs.")
