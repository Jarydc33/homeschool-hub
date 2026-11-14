from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from api.auth import require_parent
from api.errors import could_not_save, invalid
from api.schemas import LongText
from services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    message: LongText


@router.post("", status_code=201)
def send_feedback(body: FeedbackIn, background: BackgroundTasks, user=Depends(require_parent)):
    """
    Saves a parent's feedback, then emails it to Tally after replying, so
    the parent doesn't wait on the email.
    """

    if not body.message:
        raise invalid("Please write a message.")

    saved = FeedbackService.submit(body.message)

    if saved is None:
        raise could_not_save()

    background.add_task(FeedbackService.email, saved)

    return {"status": "sent"}
