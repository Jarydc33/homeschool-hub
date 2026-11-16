"""Hours tracking: minutes saved at check-off, parents' adjustments, totals."""
from datetime import date, timedelta
from unittest import mock

import pytest

from api_support import as_
from database.models import AssignmentOccurrence, UserRole
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.hours_service import MAX_MINUTES, HoursService
from services.pe_service import PEService
from services.student_service import StudentService
from services.subject_service import SubjectService

TODAY = date(2026, 11, 4)
YESTERDAY = TODAY - timedelta(days=1)
WEEK_AGO = TODAY - timedelta(days=7)

SMITH = as_("smith_parent")
JONES = as_("jones_parent")
BOB = as_("bob")


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def _work(w, subject, title="Lesson", due=TODAY, students=None, minutes=None):
    return AssignmentService.create_assignment(
        subject_id=subject,
        title=title,
        student_ids=[w.ann] if students is None else students,
        due_date=due,
        minutes=minutes,
    )


def _row(assignment, student_id, day=TODAY):
    return next(
        row
        for row in StudentService.get_student_occurrences(student_id)
        if row.assignment_id == assignment.id and row.occurrence_date == day
    )


def _check(assignment, student_id, done=True, day=TODAY):
    return StudentService.update_occurrence_status(_row(assignment, student_id, day).id, done)


# ----- Minutes at check-off -----


def test_checking_off_saves_the_subjects_usual_time(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45)
    work = _work(w, w.math)

    assert _check(work, w.ann).minutes == 45


def test_an_assignments_minutes_override_the_subject(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45)
    work = _work(w, w.math, minutes=20)

    assert _check(work, w.ann).minutes == 20


def test_work_with_no_time_set_counts_none(parent):
    w = parent
    work = _work(w, w.math)

    assert _check(work, w.ann).minutes is None


def test_unchecking_clears_the_minutes(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45)
    work = _work(w, w.math)
    _check(work, w.ann)

    assert _check(work, w.ann, done=False).minutes is None


def test_checking_off_again_keeps_a_parents_adjustment(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45)
    work = _work(w, w.math)
    row = _check(work, w.ann)
    HoursService.set_minutes(row.id, 70)

    assert _check(work, w.ann).minutes == 70


def test_changing_a_subjects_time_later_keeps_past_hours(parent, fetch):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45)
    work = _work(w, w.math)
    row = _check(work, w.ann)

    SubjectService.update_subject(w.math, default_minutes=90)

    assert fetch(AssignmentOccurrence, row.id).minutes == 45


# ----- Setting minutes on subjects and assignments -----


def test_subjects_and_assignments_refuse_impossible_minutes(parent):
    w = parent

    assert SubjectService.create_subject("Too long", default_minutes=MAX_MINUTES + 1) is None
    assert SubjectService.create_subject("Zero", default_minutes=0) is None
    assert SubjectService.update_subject(w.math, default_minutes=-5) is None
    assert _work(w, w.math, minutes=MAX_MINUTES + 1) is None


def test_updating_a_subject_without_minutes_keeps_them(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45, is_core=True)

    subject = SubjectService.update_subject(w.math, name="Maths")

    assert subject.default_minutes == 45
    assert subject.is_core is True

    assert SubjectService.update_subject(w.math, default_minutes=None).default_minutes is None


def test_students_cant_change_a_subjects_time(world, login):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert SubjectService.update_subject(world.math, default_minutes=45) is None


# ----- Adjusting a day's minutes -----


def test_a_parent_can_adjust_finished_work_including_to_zero(parent, fetch):
    w = parent
    work = _work(w, w.math, minutes=30)
    row = _check(work, w.ann)

    assert HoursService.set_minutes(row.id, 0)
    assert fetch(AssignmentOccurrence, row.id).minutes == 0


def test_unfinished_work_cant_get_minutes(parent):
    w = parent
    work = _work(w, w.math, minutes=30)

    assert HoursService.set_minutes(_row(work, w.ann).id, 30) is None


def test_adjusting_refuses_impossible_minutes(parent):
    w = parent
    row = _check(_work(w, w.math, minutes=30), w.ann)

    assert HoursService.set_minutes(row.id, MAX_MINUTES + 1) is None
    assert HoursService.set_minutes(row.id, -1) is None
    assert HoursService.set_minutes(row.id, None) is None


def test_students_cant_adjust_minutes(world, login):
    login(world.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        row = _check(_work(world, world.math, students=[world.bob], minutes=30), world.bob)

    login(world.smith, UserRole.STUDENT, world.bob)

    assert HoursService.set_minutes(row.id, 90) is None


def test_another_family_cant_adjust_minutes(world, login, fetch):
    login(world.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        row = _check(_work(world, world.math, minutes=30), world.ann)

    login(world.jones)

    assert HoursService.set_minutes(row.id, 90) is None
    assert fetch(AssignmentOccurrence, row.id).minutes == 30


# ----- Totals -----


def test_totals_by_subject_core_pe_and_school_days(parent):
    w = parent
    SubjectService.update_subject(w.math, default_minutes=45, is_core=True)
    SubjectService.update_subject(w.art, default_minutes=30)
    _check(_work(w, w.math, due=TODAY), w.ann)
    _check(_work(w, w.math, title="Yesterday", due=YESTERDAY), w.ann, day=YESTERDAY)
    _check(_work(w, w.art, title="Painting", due=TODAY), w.ann)
    PEService.log_activity([w.ann], WEEK_AGO, "Soccer", 60)

    summary = HoursService.summary(
        HoursService.get_rows(w.ann, WEEK_AGO, TODAY),
        HoursService.get_pe_logs(w.ann, WEEK_AGO, TODAY),
    )

    assert summary["total_minutes"] == 45 + 45 + 30 + 60
    assert summary["core_minutes"] == 90
    assert summary["pe_minutes"] == 60
    assert summary["school_days"] == 3
    assert [line["minutes"] for line in summary["subjects"]] == [90, 60, 30]
    assert summary["subjects"][1]["pe"] is True
    assert [day["date"] for day in summary["days"]] == [TODAY, YESTERDAY, WEEK_AGO]
    assert summary["days"][0]["minutes"] == 75


def test_totals_only_cover_the_dates_asked_for(parent):
    w = parent
    _check(_work(w, w.math, due=YESTERDAY, minutes=40), w.ann, day=YESTERDAY)

    assert HoursService.get_rows(w.ann, TODAY, TODAY) == []
    assert len(HoursService.get_rows(w.ann, YESTERDAY, TODAY)) == 1


def test_a_day_adjusted_to_zero_isnt_a_school_day(parent):
    w = parent
    row = _check(_work(w, w.math, minutes=40), w.ann)
    HoursService.set_minutes(row.id, 0)

    summary = HoursService.summary(HoursService.get_rows(w.ann, TODAY, TODAY), [])

    assert summary["school_days"] == 0


def test_archived_work_still_counts(parent):
    w = parent
    work = _work(w, w.math, minutes=40)
    _check(work, w.ann)

    AssignmentService.archive_assignment(work.id)

    assert len(HoursService.get_rows(w.ann, TODAY, TODAY)) == 1


def test_another_family_cant_read_hours(world, login):
    login(world.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        _check(_work(world, world.math, minutes=40), world.ann)

    login(world.jones)

    assert HoursService.get_rows(world.ann, TODAY, TODAY) == []


def test_a_student_cant_read_a_siblings_hours(world, login):
    login(world.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        _check(_work(world, world.math, minutes=40), world.ann)

    login(world.smith, UserRole.STUDENT, world.bob)

    assert HoursService.get_rows(world.ann, TODAY, TODAY) == []


# ----- The API -----


def test_api_hours_report_and_adjusting(api, world):
    api.put(
        f"/subjects/{world.math}",
        json={"name": "Math", "default_minutes": 45, "is_core": True},
        headers=SMITH,
    )
    created = api.post(
        "/assignments",
        json={
            "title": "Fractions",
            "subject_id": world.math,
            "student_ids": [world.bob],
            "due_date": TODAY.isoformat(),
        },
        headers=SMITH,
    ).json()
    occurrence = next(
        row
        for row in api.get(f"/students/{world.bob}/dashboard", headers=SMITH).json()["overdue"]
        + api.get(f"/students/{world.bob}/dashboard", headers=SMITH).json()["today_work"]
        + api.get(f"/students/{world.bob}/dashboard", headers=SMITH).json()["upcoming"]
        if row["assignment_id"] == created["id"]
    )
    api.put(
        f"/occurrences/{occurrence['occurrence_id']}/completed",
        json={"completed": True},
        headers=BOB,
    )

    window = {"start": TODAY.isoformat(), "end": TODAY.isoformat()}
    report = api.get(f"/students/{world.bob}/hours", params=window, headers=SMITH).json()

    assert report["total_minutes"] == 45
    assert report["core_minutes"] == 45
    assert report["subjects"][0]["name"] == "Math"
    assert report["days"][0]["work"][0]["title"] == "Fractions"

    # Bob can read his own, but only a parent adjusts.
    assert api.get(f"/students/{world.bob}/hours", params=window, headers=BOB).status_code == 200
    minutes_url = f"/occurrences/{occurrence['occurrence_id']}/minutes"
    assert api.put(minutes_url, json={"minutes": 60}, headers=BOB).status_code == 403
    assert api.put(minutes_url, json={"minutes": 601}, headers=SMITH).status_code == 422
    assert api.put(minutes_url, json={"minutes": 60}, headers=SMITH).status_code == 200

    report = api.get(f"/students/{world.bob}/hours", params=window, headers=SMITH).json()
    assert report["total_minutes"] == 60


def test_api_hours_are_private_to_the_family(api, world):
    assert api.get(f"/students/{world.bob}/hours", headers=JONES).status_code == 404


def test_api_refuses_backwards_dates(api, world):
    params = {"start": TODAY.isoformat(), "end": YESTERDAY.isoformat()}

    assert api.get(f"/students/{world.bob}/hours", params=params, headers=SMITH).status_code == 400


def test_api_subject_minutes_are_kept_when_left_out(api, world):
    api.put(
        f"/subjects/{world.math}",
        json={"name": "Math", "default_minutes": 45, "is_core": True},
        headers=SMITH,
    )

    renamed = api.put(f"/subjects/{world.math}", json={"name": "Maths"}, headers=SMITH).json()

    assert renamed["default_minutes"] == 45
    assert renamed["is_core"] is True
