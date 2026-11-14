"""
Feedback from parents: saved in the feedback table, then emailed to Tally.

Saving is what counts. The email is a convenience, sent after the parent's
request finishes, so a slow or failed email never loses the message.
"""
from dataclasses import dataclass

from config import get_optional_setting
from database.db import get_session
from database.models import Family, Feedback
from services.current_user import CurrentUser
from services.email_service import EmailService

# Where feedback emails go. FEEDBACK_EMAIL overrides it.
DEFAULT_FEEDBACK_EMAIL = "hello@tallyhomeschool.com"


@dataclass
class FeedbackEmail:
    """Everything the email needs, so sending it doesn't need the request."""

    sender_email: str
    family_name: str
    message: str


class FeedbackService:

    @staticmethod
    def submit(message):
        """
        Saves a parent's feedback. Returns a FeedbackEmail to send, or None
        if it wasn't saved (not a parent, or a blank message).
        """

        message = (message or "").strip()

        if not message or not CurrentUser.is_parent():
            return None

        user = CurrentUser.get()
        family_id = CurrentUser.get_family_id()

        if user is None or family_id is None:
            return None

        with get_session() as db:

            family = (
                db.query(Family)
                .filter(Family.id == family_id)
                .first()
            )

            db.add(
                Feedback(
                    family_id=family_id,
                    user_id=user.id,
                    message=message,
                )
            )

            db.commit()

        return FeedbackEmail(
            sender_email=user.email,
            family_name=family.family_name if family else "",
            message=message,
        )

    @staticmethod
    def email(feedback):
        """Emails saved feedback to Tally, with replies going to the parent."""

        to = get_optional_setting("FEEDBACK_EMAIL") or DEFAULT_FEEDBACK_EMAIL

        who = feedback.family_name or feedback.sender_email

        text = (
            f"{feedback.message}\n\n"
            "---\n"
            f"From: {feedback.sender_email}\n"
            f"Family: {feedback.family_name}\n"
            "Reply to this email to answer them.\n"
        )

        return EmailService.send(
            to,
            f"tally feedback from {who}",
            text,
            reply_to=feedback.sender_email,
        )
