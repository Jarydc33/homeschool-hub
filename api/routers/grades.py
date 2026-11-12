from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_parent, signed_in
from api.errors import invalid, not_found
from api.schemas import Message, Name, WorkItem, work_item
from services.current_user import CurrentUser
from services.grade_service import GradeService
from services.student_service import StudentService

router = APIRouter(tags=["grades"])

STUDENT_NOT_FOUND = "This student could not be found."

PERIOD_NOT_FOUND = "This grading period could not be found."

WORK_NOT_FOUND = "This work could not be found."


class Grade(BaseModel):
    """A percent with its letter, such as 92.0 and "A"."""

    percent: float
    letter: str


class GradedWork(BaseModel):
    work: WorkItem
    score: float
    points_possible: float
    grade: Grade


class SubjectGrade(BaseModel):
    subject: str
    grade: Grade


class PeriodOut(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date


class PeriodComparison(BaseModel):
    period_id: int
    grade: Grade


class SubjectComparison(BaseModel):
    subject: str
    periods: list[PeriodComparison]


class Report(BaseModel):
    period: PeriodOut | None
    overall: Grade | None
    subjects: list[SubjectGrade]
    work: list[GradedWork]
    # Each subject across every period, and the overall, to compare terms.
    comparison: list[SubjectComparison]
    overall_by_period: list[PeriodComparison]


class GradingQueue(BaseModel):
    # Checked off but not graded yet, oldest first.
    finished: list[WorkItem]
    # Not checked off, from the last 30 days through the next 7.
    unfinished: list[WorkItem]
    # Points to suggest per assignment id, from its latest grade.
    suggested_totals: dict[int, float]


class GradeIn(BaseModel):
    score: float = Field(ge=0)
    points_possible: float = Field(gt=0)


class PeriodIn(BaseModel):
    name: Name
    start_date: date
    end_date: date


def _grade(percent):

    if percent is None:
        return None

    return Grade(percent=round(float(percent), 1), letter=GradeService.letter(percent))


def _period_out(period):

    return PeriodOut(
        id=period.id,
        name=period.name,
        start_date=period.start_date,
        end_date=period.end_date,
    )


# ----- A student's grades -----


@router.get("/students/{student_id}/grades", response_model=Report)
def report(student_id: int, period_id: int | None = None, user=Depends(signed_in)):
    """
    A student's grades, for one grading period or all time. Students see
    their own; parents any of theirs. A blank score never counts.
    """

    if not StudentService.get_student_by_id(student_id):
        raise not_found(STUDENT_NOT_FOUND)

    periods = GradeService.get_periods()

    period = None

    if period_id is not None:

        period = next((p for p in periods if p.id == period_id), None)

        if not period:
            raise not_found(PERIOD_NOT_FOUND)

    all_rows = GradeService.get_graded_rows(student_id)

    rows = GradeService.rows_in_period(all_rows, period)

    subject_percents = GradeService.subject_percents(rows)

    comparison = GradeService.comparison(all_rows, periods)

    return Report(
        period=_period_out(period) if period else None,
        overall=_grade(GradeService.overall_percent(subject_percents)),
        subjects=[
            SubjectGrade(subject=name, grade=_grade(percent))
            for name, percent in sorted(subject_percents.items())
        ],
        work=[
            GradedWork(
                work=work_item(row),
                score=float(row.score),
                points_possible=float(row.points_possible),
                grade=_grade(GradeService.percent(row)),
            )
            for row in rows
        ],
        comparison=[
            SubjectComparison(
                subject=name,
                periods=[
                    PeriodComparison(period_id=pid, grade=_grade(percent))
                    for pid, percent in by_period.items()
                ],
            )
            for name, by_period in sorted(comparison["subjects"].items())
        ],
        overall_by_period=[
            PeriodComparison(period_id=pid, grade=_grade(percent))
            for pid, percent in comparison["overall"].items()
        ],
    )


# ----- Grading (parents) -----


@router.get("/students/{student_id}/grading", response_model=GradingQueue)
def grading_queue(student_id: int, user=Depends(require_parent)):
    """What a parent can grade for a student, on active graded assignments."""

    if not StudentService.get_student_by_id(student_id):
        raise not_found(STUDENT_NOT_FOUND)

    work = GradeService.get_work_to_grade(student_id, CurrentUser.get_today())

    return GradingQueue(
        finished=[work_item(row) for row in work["finished"]],
        unfinished=[work_item(row) for row in work["unfinished"]],
        suggested_totals={
            assignment_id: float(points)
            for assignment_id, points in GradeService.suggested_totals(
                work["finished"] + work["unfinished"]
            ).items()
        },
    )


@router.put("/occurrences/{occurrence_id}/grade", response_model=Message)
def set_grade(occurrence_id: int, body: GradeIn, user=Depends(require_parent)):
    """Saves a grade. It doesn't check the work off."""

    error = GradeService.grade_error(body.score, body.points_possible)

    if error:
        raise invalid(error)

    if not GradeService.set_grade(occurrence_id, body.score, body.points_possible):
        raise not_found(WORK_NOT_FOUND)

    return Message(message="Grade saved.")


@router.delete("/occurrences/{occurrence_id}/grade", response_model=Message)
def clear_grade(occurrence_id: int, user=Depends(require_parent)):
    """Removes a grade, so the work stops counting."""

    if not GradeService.clear_grade(occurrence_id):
        raise not_found(WORK_NOT_FOUND)

    return Message(message="Grade removed.")


# ----- Grading periods -----


@router.get("/grading-periods", response_model=list[PeriodOut])
def list_periods(user=Depends(signed_in)):
    """The family's grading periods, earliest first."""

    return [_period_out(period) for period in GradeService.get_periods()]


@router.post("/grading-periods", response_model=PeriodOut, status_code=201)
def create_period(body: PeriodIn, user=Depends(require_parent)):
    """Periods can't overlap. A grade belongs to the period its date falls in."""

    error = GradeService.period_error(body.name, body.start_date, body.end_date)

    if error:
        raise invalid(error)

    period = GradeService.create_period(body.name, body.start_date, body.end_date)

    if not period:
        raise invalid("This grading period couldn't be saved.")

    return _period_out(period)


@router.put("/grading-periods/{period_id}", response_model=PeriodOut)
def update_period(period_id: int, body: PeriodIn, user=Depends(require_parent)):

    error = GradeService.period_error(
        body.name, body.start_date, body.end_date, period_id
    )

    if error:
        raise invalid(error)

    period = GradeService.update_period(
        period_id, body.name, body.start_date, body.end_date
    )

    if not period:
        raise not_found(PERIOD_NOT_FOUND)

    return _period_out(period)


@router.post("/grading-periods/{period_id}/archive", response_model=Message)
def archive_period(period_id: int, user=Depends(require_parent)):
    """Removes a period. Grades aren't touched, since they go by date."""

    if not GradeService.archive_period(period_id):
        raise not_found(PERIOD_NOT_FOUND)

    return Message(message="Grading period removed.")
