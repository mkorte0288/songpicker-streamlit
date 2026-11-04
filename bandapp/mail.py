import json
from email.utils import parseaddr
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoEmailBackend(BaseEmailBackend):
    endpoint = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or ():
            name, email = parseaddr(message.from_email)
            sender = {"email": email}
            if name:
                sender["name"] = name
            payload = {
                "sender": sender,
                "to": [{"email": parseaddr(recipient)[1]} for recipient in message.to],
                "subject": message.subject,
                "textContent": message.body,
            }
            request = Request(self.endpoint, data=json.dumps(payload).encode("utf-8"), headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
            try:
                with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                    if response.status != 201:
                        raise OSError("Transactional email provider did not accept the message.")
            except HTTPError as exc:
                if not self.fail_silently:
                    raise OSError(f"Transactional email provider returned HTTP {exc.code}.") from None
            except OSError:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent
