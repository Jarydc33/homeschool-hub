"""Every service opens its database session through get_session()."""
import pytest

from database.db import get_session
from database.models import Family, Student
from services.student_service import StudentService


def test_session_closes_and_drops_uncommitted_work_on_error():
    with pytest.raises(ValueError):
        with get_session() as db:
            db.add(Family(family_name="Half done"))
            db.flush()
            raise ValueError

    with get_session() as db:
        assert db.query(Family).count() == 0


def test_saved_values_stay_readable_after_the_session_closes():
    with get_session() as db:
        family = Family(family_name="Smith")
        db.add(family)
        db.commit()

    assert family.family_name == "Smith"
    assert family.id is not None


def test_a_service_return_value_is_readable_after_it_commits(smith_parent):
    archived = StudentService.archive_student(smith_parent.ann)

    assert archived.name == "Ann"
    assert archived.active is False
