from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import signed_in
from api.schemas import (
    Progress,
    StudentDashboard,
    StudentOut,
    student_out,
    work_item,
)
from services.current_user import CurrentUser
from services.daily_message_service import DailyMessageService
from services.occurrence_service import OccurrenceService
from services.student_service import StudentService

router = APIRouter(prefix="/students", tags=["students"])

NOT_FOUND_MESSAGE = "This student could not be found."


@router.get("", response_model=list[StudentOut])
def list_students(user=Depends(signed_in)):
    """
    A parent gets the family's active students; a student gets only
    themselves.
    """

    if CurrentUser.is_student():

        # The service lists the whole family, which the Streamlit pages
        # never show a student.

        student = StudentService.get_student_by_id(
            CurrentUser.get_student_id()
        )

        return [student_out(student)] if student else []

    return [
        student_out(student)
        for student in StudentService.get_current_family_students()
    ]


@router.get("/{student_id}/dashboard", response_model=StudentDashboard)
def student_dashboard(student_id: int, user=Depends(signed_in)):
    """
    A student's work for today: overdue, today's, upcoming and missed, with
    today's progress. Parents can open any of their students; a student
    only their own.
    """

    student = StudentService.get_student_by_id(student_id)

    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)

    today = CurrentUser.get_today()

    groups = OccurrenceService.group_for_student(
        StudentService.get_student_occurrences(student_id),
        today,
    )

    done, total = OccurrenceService.today_progress(groups, today)

    return StudentDashboard(
        student=student_out(student),
        today=today,
        message=DailyMessageService.get_message(today),
        progress=Progress(done=done, total=total),
        overdue=[work_item(row) for row in groups["overdue"]],
        today_work=[work_item(row) for row in groups["today"]],
        completed_today=[
            work_item(row)
            for row in groups["completed"]
            if row.occurrence_date == today
        ],
        upcoming=[work_item(row) for row in groups["upcoming"]],
        missed=[work_item(row) for row in groups["missed"]],
    )
