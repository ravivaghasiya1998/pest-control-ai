"""
Communications layer — SMS (Twilio) and email (SendGrid).
All calls are mocked when credentials are missing; just swap in real keys.
"""
from __future__ import annotations

import logging

from config import settings

log = logging.getLogger(__name__)


def send_sms(to: str, body: str) -> bool:
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        log.info("[SMS MOCK] To: %s | %s", to, body[:80])
        return True
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(body=body, from_=settings.twilio_from_number, to=to)
        return True
    except Exception as exc:
        log.warning("SMS failed to %s: %s", to, exc)
        return False


def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.sendgrid_api_key:
        log.info("[EMAIL MOCK] To: %s | Subject: %s", to, subject)
        return True
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        mail = Mail(from_email=settings.from_email, to_emails=to, subject=subject, plain_text_content=body)
        sg.client.mail.send.post(request_body=mail.get())
        return True
    except Exception as exc:
        log.warning("Email failed to %s: %s", to, exc)
        return False
