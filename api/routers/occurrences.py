from fastapi import APIRouter, Depends

from api.auth import signed_in
from api.errors import not_found
from api.schemas import Badge, CheckOff, CheckOffResult, work_item
from services.achievement_service import AchievementService
from services.current_user import CurrentUser
from services.student_service import StudentService

router = APIRouter(prefix="/occurrences", tags=["work"])

NOT_FOUND_MESSAGE = "This work could not be found."


@router.put("/{occurrence_id}/completed", response_model=CheckOffResult)
def set_completed(
    occurrence_id: int,
    body: CheckOff,
    user=Depends(signed_in),
):
    """
    Checks one day's work on or off. Students can only change their own;
    parents any of their family's. Returns any badges this earned, so the
    app can celebrate them.
    """

    row = StudentService.get_occurrence(occurrence_id)

    if not row:
        raise not_found(NOT_FOUND_MESSAGE)

    today = CurrentUser.get_today()

    before = AchievementService.summary(
        StudentService.get_student_occurrences(row.student_id),
        today,
    )

    row = StudentService.update_occurrence_status(occurrence_id, body.completed)

    if not row:
        raise not_found(NOT_FOUND_MESSAGE)

    after = AchievementService.summary(
        StudentService.get_student_occurrences(row.student_id),
        today,
    )

    return CheckOffResult(
        work=work_item(row),
        new_badges=[
            Badge(**badge)
            for badge in AchievementService.newly_earned(before, after)
        ],
    )
