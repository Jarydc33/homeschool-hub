from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import signed_in
from api.schemas import CheckOff, WorkItem, work_item
from services.student_service import StudentService

router = APIRouter(prefix="/occurrences", tags=["work"])

NOT_FOUND_MESSAGE = "This work could not be found."


@router.put("/{occurrence_id}/completed", response_model=WorkItem)
def set_completed(
    occurrence_id: int,
    body: CheckOff,
    user=Depends(signed_in),
):
    """
    Checks one day's work on or off. Students can only change their own;
    parents any of their family's.
    """

    row = StudentService.update_occurrence_status(
        occurrence_id,
        body.completed,
    )

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)

    return work_item(row)
