from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import require_parent, signed_in
from api.schemas import Banner, StudentOut, SubjectOut, banner, student_out
from services.activity_service import ActivityService
from services.assignment_service import AssignmentService
from services.banner_service import BannerService
from services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


class StudentMetrics(BaseModel):
    student: StudentOut
    total: int
    completed: int
    percent: float
    overdue_count: int


class DueWork(BaseModel):
    assignment_id: int
    title: str
    subject: SubjectOut | None
    # Overdue: who still owes it. Today: who it's due for.
    student_names: list[str]


class ActivityDay(BaseModel):
    date: date
    label: str
    items: list[str]


class ParentDashboard(BaseModel):
    today: date
    students: list[StudentMetrics]
    overdue: list[DueWork]
    due_today: list[DueWork]
    recent_activity: list[ActivityDay]
    # Students with a curriculum lesson before today that isn't done, for
    # the "Missed a Day?" prompt.
    students_behind: list[int]
    banners: list[Banner]


def _due_work(entry):

    assignment = entry["assignment"]
    subject = assignment.subject

    return DueWork(
        assignment_id=assignment.id,
        title=assignment.title,
        subject=(
            SubjectOut(id=subject.id, name=subject.name, color=subject.color)
            if subject
            else None
        ),
        student_names=entry["student_names"],
    )


@router.get("/dashboard", response_model=ParentDashboard)
def parent_dashboard(user=Depends(require_parent)):
    """Everything the Parent Dashboard shows."""

    data = DashboardService.get_dashboard_data()

    today = data["today"]

    return ParentDashboard(
        today=today,
        students=[
            StudentMetrics(
                student=student_out(student),
                **DashboardService.get_student_metrics(student),
            )
            for student in data["students"]
        ],
        overdue=[_due_work(entry) for entry in data["overdue_assignments"]],
        due_today=[_due_work(entry) for entry in data["today_assignments"]],
        recent_activity=[
            ActivityDay(
                date=day,
                label=ActivityService.day_label(day, today),
                items=items,
            )
            for day, items in ActivityService.get_recent(today)
        ],
        students_behind=sorted(AssignmentService.get_students_behind(today)),
        banners=[banner(row) for row in BannerService.get_active_banners()],
    )


@router.get("/banners", response_model=list[Banner])
def active_banners(user=Depends(signed_in)):
    """Announcements showing now: the family's and system-wide ones."""

    return [banner(row) for row in BannerService.get_active_banners()]
