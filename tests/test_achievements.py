"""Streaks and badges come from a student's occurrences when read."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import User, UserRole
from services.achievement_service import AchievementService
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.session_service import SessionService
from services.student_service import StudentService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday.
TODAY = date(2026, 11, 5)


def day(offset):
    return TODAY + timedelta(days=offset)


def row(offset, done=True, assignment_id=1, kind="Recurring"):
    return SimpleNamespace(
        occurrence_date=day(offset),
        status="Complete" if done else "Not Started",
        assignment_id=assignment_id,
        assignment=SimpleNamespace(assignment_type=kind),
    )


def summary(rows):
    return AchievementService.summary(rows, TODAY)


def earned(rows):
    return {
        badge["key"]
        for badge in summary(rows)["badges"]
        if badge["earned"]
    }


# ----- Streaks -----


def test_no_work_means_no_streak():
    assert summary([])["streak"] == 0
    assert summary([])["best_streak"] == 0


def test_days_in_a_row_count():
    assert summary([row(-2), row(-1), row(0)])["streak"] == 3


def test_a_day_counts_only_when_all_its_work_is_done():
    rows = [row(-2), row(-1), row(-1, done=False), row(0)]

    assert summary(rows)["streak"] == 1


def test_unfinished_today_doesnt_break_the_streak():
    assert summary([row(-2), row(-1), row(0, done=False)])["streak"] == 2


def test_days_with_no_work_dont_break_the_streak():
    # Friday, then the weekend off, then Monday.
    assert summary([row(-6), row(-3)])["streak"] == 2


def test_a_missed_day_breaks_the_streak_and_best_is_kept():
    rows = [row(-5), row(-4), row(-3), row(-2, done=False), row(-1)]

    result = summary(rows)

    assert result["streak"] == 1
    assert result["best_streak"] == 3


def test_catching_up_repairs_the_streak():
    assert summary([row(-3), row(-2, done=False), row(-1)])["streak"] == 1
    assert summary([row(-3), row(-2, done=True), row(-1)])["streak"] == 3


def test_future_work_done_early_doesnt_count():
    assert summary([row(-1), row(1), row(2)])["streak"] == 1


# ----- Badges -----


def test_no_work_earns_no_badges():
    assert earned([]) == set()


def test_completed_badges_count_finished_work():
    rows = [row(-offset) for offset in range(10)]

    assert {"completed_1", "completed_10"} <= earned(rows)
    assert "completed_50" not in earned(rows)


def test_unfinished_work_earns_nothing():
    assert "completed_1" not in earned([row(-1, done=False)])


def test_streak_badges_go_by_the_best_streak():
    rows = [row(-offset) for offset in range(3, 8)] + [row(-1, done=False)]

    result = earned(rows)

    assert {"streak_3", "streak_5"} <= result
    assert "streak_10" not in result


def test_a_finished_week_with_everything_done_is_perfect():
    # Monday to Wednesday of last week.
    assert "perfect_week" in earned([row(-10), row(-9), row(-8)])


def test_a_week_with_a_missed_day_isnt_perfect():
    rows = [row(-10), row(-9), row(-8, done=False)]

    assert "perfect_week" not in earned(rows)


def test_a_light_week_isnt_perfect():
    assert "perfect_week" not in earned([row(-10), row(-9)])


def test_the_current_week_isnt_perfect_until_its_over():
    # Monday to today, this week.
    assert "perfect_week" not in earned([row(-3), row(-2), row(-1), row(0)])


def test_curriculum_badges_follow_lessons_done():
    def lesson(done):
        return row(-1, done=done, kind="Curriculum")

    assert "halfway" not in earned([lesson(True), lesson(False), lesson(False)])
    assert "halfway" in earned([lesson(True), lesson(False)])
    assert "finisher" not in earned([lesson(True), lesson(False)])
    assert "finisher" in earned([lesson(True), lesson(True)])


def test_other_work_doesnt_earn_curriculum_badges():
    assert not {"halfway", "finisher"} & earned([row(-1), row(-2)])


def test_newly_earned_finds_only_new_badges():
    before = summary([row(-1, done=False)])
    after = summary([row(-1)])

    assert [badge["key"] for badge in AchievementService.newly_earned(before, after)] == [
        "completed_1"
    ]
    assert AchievementService.newly_earned(after, after) == []


# ----- With real rows -----


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def _curriculum(w, start=TODAY):
    return AssignmentService.create_assignment(
        subject_id=w.math,
        title="Saxon Math",
        student_ids=[w.bob],
        due_date=start,
        assignment_type="Curriculum",
        recurrence_pattern="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
        lesson_count=4,
    )


def test_a_shifted_day_doesnt_break_the_streak(parent):
    _curriculum(parent, start=day(-3))

    first_lesson = next(
        r
        for r in StudentService.get_student_occurrences(parent.bob)
        if r.lesson_number == 1
    )
    StudentService.update_occurrence_status(first_lesson.id, True)

    # The next two lessons were missed, which breaks the streak...
    assert summary(StudentService.get_student_occurrences(parent.bob))["streak"] == 0

    # ...until shifting moves them off the days that were missed.
    AssignmentService.shift_lessons([parent.bob], TODAY)

    assert summary(StudentService.get_student_occurrences(parent.bob))["streak"] == 1


def test_one_family_cant_see_anothers_achievements(parent, login):
    _curriculum(parent)
    rows = StudentService.get_student_occurrences(parent.bob)
    StudentService.update_occurrence_status(rows[0].id, True)

    login(parent.jones)

    assert earned(StudentService.get_student_occurrences(parent.bob)) == set()


def test_a_student_cant_see_a_siblings_achievements(parent, login):
    _curriculum(parent)
    rows = StudentService.get_student_occurrences(parent.bob)
    StudentService.update_occurrence_status(rows[0].id, True)

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.ann)

    assert earned(StudentService.get_student_occurrences(parent.bob)) == set()


# ----- The page -----


@pytest.fixture
def student_page(world):
    db = SessionLocal()
    try:
        user = User(
            family_id=world.smith,
            student_id=world.bob,
            email="bob@smith.test",
            auth_user_id="00000000-0000-0000-0000-00000000000b",
            role="Student",
        )
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    def _open():
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob("*_Student_Dashboard.py"))),
            default_timeout=30,
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield _open


def test_page_shows_the_streak_and_earns_a_badge(world, login, student_page):
    w = world
    today = date.today()
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=today):
        _curriculum(w, start=today)
    mock.patch.stopall()

    at = student_page().run()

    assert not at.exception
    assert next(m for m in at.metric if "Streak" in m.label).value == "0 days"
    assert any("Badges (0 of" in s.value for s in at.subheader)

    next(c for c in at.checkbox if "Lesson 1" in c.label).check().run()

    assert not at.exception
    assert next(m for m in at.metric if "Streak" in m.label).value == "1 day"
    assert any("Badges (1 of" in s.value for s in at.subheader)
    assert any("First Step" in text.value for text in at.markdown)
