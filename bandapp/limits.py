from datetime import datetime, timezone
from ipaddress import IPv6Address, ip_address, ip_network

from django.conf import settings

from django.db.models import F
from django.http import HttpResponse
from django.utils.crypto import salted_hmac

from .models import RequestLimit


def client_identity(meta):
    """Read the verified proxy suffix only when the deployment opts in."""
    peer = meta.get("REMOTE_ADDR", "")
    hops = settings.TRUSTED_PROXY_HOPS
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    if hops and len(forwarded) <= 2048:
        addresses = forwarded.split(",")
        if len(addresses) >= hops:
            try:
                chain = [ip_address(value.strip()) for value in addresses[-hops:]]
                peer = str(chain[0])
            except ValueError:
                pass
    try:
        address = ip_address(peer)
    except ValueError:
        return "unknown"
    if isinstance(address, IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ip_network(f"{address}/64", strict=False))
    return str(address)


class AccountLimits:
    limits = {
        "login": (25, 900),
        "signup": (8, 3600),
        "resend": (6, 3600),
        "activate": (15, 900),
        "password_reset": (8, 3600),
        "password_reset_confirm": (15, 900),
        "invite": (25, 3600),
        "transfer_admin": (12, 900),
        "delete_band": (12, 900),
        "delete_account": (12, 900),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view, args, kwargs):
        if request.method != "POST":
            return None
        route = request.resolver_match.url_name
        if route not in self.limits:
            return None

        maximum, interval = self.limits[route]
        now = datetime.now(timezone.utc)
        window = int(now.timestamp()) // interval
        expires = datetime.fromtimestamp((window + 1) * interval, timezone.utc)
        identities = [f"ip:{client_identity(request.META)}"]
        email = request.POST.get("email", "").strip().lower()[:254]
        if email and route in {"signup", "resend", "password_reset"}:
            identities.append(f"mail:{email}")
        if route in {"invite", "transfer_admin", "delete_band", "delete_account"} and request.user.is_authenticated:
            identities = [f"account:{request.user.pk}"]

        RequestLimit.objects.filter(expires__lte=now).delete()
        for identity in identities:
            key = salted_hmac("songpicker-limit", f"{route}:{window}:{identity}", algorithm="sha256").hexdigest()
            RequestLimit.objects.get_or_create(key=key, defaults={"expires": expires})
            updated = RequestLimit.objects.filter(pk=key, attempts__lt=maximum).update(attempts=F("attempts") + 1)
            if not updated:
                return HttpResponse("Zu viele Versuche. Bitte versuche es später erneut.", status=429,
                                    headers={"Retry-After": str(max(1, int((expires - now).total_seconds())))})
        return None
