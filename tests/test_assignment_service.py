from datetime import date

from database.db import SessionLocal
from database.models import Assignment, StudentAssignment
from services.assignment_service import AssignmentService


def links_for(assignment_id):
    db = SessionLocal()
    try:
        return {
            link.student_id: link
            for link in db.query(StudentAssignment).filter_by(
                assignment_id=assignment_id
            )
        }
    finally:
        db.close()


def edit(world, assignment=None, subject=None, students=None, title="Edited"):
    return AssignmentService.update_assignment(
        assignment_id=assignment or world.essay,
        title=title,
        description="New description",
        due_date=date(2026, 12, 1),
        subject_id=subject or world.art,
        student_ids=[world.ann, world.bob] if students is None else students,
        assignment_type="One Time",
        recurrence_pattern=None,
    )


# ----- update_assignment: progress is kept -----


def test_edit_changes_fields(smith_parent, fetch):
    w = smith_parent

    assert edit(w, subject=w.math).title == "Edited"

    saved = fetch(Assignment, w.essay)
    assert saved.title == "Edited"
    assert saved.description == "New description"
    assert saved.due_date == date(2026, 12, 1)
    assert saved.subject_id == w.math


def test_edit_keeps_completed_students_progress(smith_parent):
    w = smith_parent

    edit(w)

    ann = links_for(w.essay)[w.ann]
    assert ann.status == "Complete"
    assert ann.completed_at == w.done_at
    assert ann.notes == "Well done"


def test_edit_does_not_recreate_rows(smith_parent):
    w = smith_parent
    before = {sid: link.id for sid, link in links_for(w.essay).items()}

    edit(w)

    after = {sid: link.id for sid, link in links_for(w.essay).items()}
    assert after == before


def test_edit_adds_and_removes_only_what_changed(smith_parent):
    w = smith_parent

    edit(w, students=[w.ann, w.cat])

    links = links_for(w.essay)
    assert w.bob not in links
    assert links[w.cat].status == "Not Started"
    assert links[w.ann].status == "Complete"


def test_edit_ignores_duplicate_students(smith_parent):
    w = smith_parent

    edit(w, students=[w.ann, w.bob, w.cat, w.cat])

    assert len([sid for sid in links_for(w.essay) if sid == w.cat]) == 1


# ----- update_assignment: archived rows -----


def test_edit_keeps_archived_students_link(smith_parent):
    w = smith_parent

    edit(w)

    assert links_for(w.essay)[w.gone].status == "Complete"


def test_edit_can_keep_existing_archived_subject(smith_parent, fetch):
    w = smith_parent

    assert edit(w, assignment=w.on_old, subject=w.old_subject, students=[])
    assert fetch(Assignment, w.on_old).subject_id == w.old_subject


def test_edit_cannot_newly_choose_archived_subject(smith_parent, fetch):
    w = smith_parent

    assert edit(w, subject=w.old_subject) is None
    assert fetch(Assignment, w.essay).subject_id == w.art


def test_edit_cannot_newly_add_archived_student(smith_parent):
    w = smith_parent

    assert edit(w, students=[w.ann, w.other_gone]) is None
    assert w.other_gone not in links_for(w.essay)


# ----- update_assignment: family checks -----


def test_edit_refuses_other_familys_assignment(smith_parent, fetch):
    w = smith_parent

    result = edit(
        w,
        assignment=w.jones_work,
        subject=w.jones_subject,
        students=[w.jones_kid],
    )

    assert result is None
    assert fetch(Assignment, w.jones_work).title == "Jones work"


def test_edit_refuses_other_familys_subject(smith_parent, fetch):
    w = smith_parent

    assert edit(w, subject=w.jones_subject) is None
    assert fetch(Assignment, w.essay).title == "Essay"


def test_edit_refused_student_applies_nothing(smith_parent, fetch):
    w = smith_parent
    before = set(links_for(w.essay))

    assert edit(w, students=[w.cat, w.jones_kid]) is None

    assert fetch(Assignment, w.essay).title == "Essay"
    assert set(links_for(w.essay)) == before


def test_edit_refuses_missing_assignment(smith_parent):
    assert edit(smith_parent, assignment=999999) is None


# ----- create_assignment -----


def create(world, subject=None, students=None):
    return AssignmentService.create_assignment(
        subject_id=subject,
        title="New work",
        student_ids=[world.ann, world.bob] if students is None else students,
    )


def assignment_count():
    db = SessionLocal()
    try:
        return db.query(Assignment).count()
    finally:
        db.close()


def test_create_links_students_to_current_family(smith_parent, fetch):
    w = smith_parent

    created = create(w, subject=w.math)

    assert fetch(Assignment, created.id).family_id == w.smith
    assert set(links_for(created.id)) == {w.ann, w.bob}


def test_create_refuses_bad_subjects(smith_parent):
    w = smith_parent
    before = assignment_count()

    assert create(w, subject=w.jones_subject) is None
    assert create(w, subject=w.old_subject) is None
    assert create(w, subject=None) is None

    assert assignment_count() == before


def test_create_refuses_bad_students_and_saves_nothing(smith_parent):
    w = smith_parent
    before = assignment_count()

    assert create(w, subject=w.math, students=[w.ann, w.jones_kid]) is None
    assert create(w, subject=w.math, students=[w.gone]) is None

    assert assignment_count() == before


def test_create_commits_once(smith_parent):
    w = smith_parent
    commits = []

    from sqlalchemy import event

    from database.db import engine

    def count(connection):
        commits.append(1)

    event.listen(engine, "commit", count)
    try:
        create(w, subject=w.math)
    finally:
        event.remove(engine, "commit", count)

    assert len(commits) == 1
