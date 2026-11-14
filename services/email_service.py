"""
Sends the app's own emails (not sign-in emails, which Supabase sends)
through Resend's API, from hello@tallyhomeschool.com.

Needs RESEND_API_KEY. Without it, nothing is sent and a warning is logged,
so local runs and tests never email anyone.
"""
import logging

import httpx

from config import get_optional_setting

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"

SENDER = "tally <hello@tallyhomeschool.com>"


class EmailService:

    @staticmethod
    def send(to, subject, text, reply_to=None):
        """
        Sends a plain-text email. Returns True if Resend accepted it. Never
        raises: a failure is logged, without the key or the message.
        """

        api_key = get_optional_setting("RESEND_API_KEY")

        if not api_key:
            logger.warning("Not sending an email: RESEND_API_KEY is not set.")
            return False

        payload = {
            "from": SENDER,
            "to": [to],
            "subject": subject,
            "text": text,
        }

        if reply_to:
            payload["reply_to"] = reply_to

        try:

            response = httpx.post(
                RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )

        except httpx.HTTPError as ex:
            logger.warning("Sending an email failed: %s", type(ex).__name__)
            return False

        if response.status_code >= 300:
            logger.warning("Resend refused an email: HTTP %s", response.status_code)
            return False

        return True
