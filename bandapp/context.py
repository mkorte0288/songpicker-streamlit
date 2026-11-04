from django.conf import settings


def public_settings(request):
    return {
        "public_signup": settings.PUBLIC_SIGNUP or bool(settings.PREFLIGHT_SIGNUP_EMAILS),
        "legal_notice_url": settings.LEGAL_NOTICE_URL,
        "privacy_notice_url": settings.PRIVACY_NOTICE_URL,
    }
