import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("SONGPICKER_DEV") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "django-insecure-local-songpicker-development-only" if DEBUG else ""
)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "").split(",")
PUBLIC_URL = os.environ.get("SONGPICKER_PUBLIC_URL", "http://localhost:8000" if DEBUG else "").rstrip("/")
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
                  "django.contrib.messages.context_processors.messages",
              ]}}]
DATABASES = {"default": (
    {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "songpicker.sqlite3"} if DEBUG else
    {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ["PGDATABASE"],
     "USER": os.environ["PGUSER"], "PASSWORD": os.environ["PGPASSWORD"], "HOST": os.environ["PGHOST"],
     "PORT": os.environ.get("PGPORT", "5432"), "OPTIONS": {"sslmode": os.environ.get("PGSSLMODE", "require")}}
)}
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
EMAIL_BACKEND = ("django.core.mail.backends.console.EmailBackend" if DEBUG
                 else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("SMTP_FROM", "songpicker@example.invalid" if DEBUG else "")
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
if os.environ.get("TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    if not (SECRET_KEY and PUBLIC_URL.startswith("https://") and EMAIL_HOST and DEFAULT_FROM_EMAIL):
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY, HTTPS SONGPICKER_PUBLIC_URL, SMTP_HOST and SMTP_FROM.")
