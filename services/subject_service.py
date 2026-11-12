# services/subject_service.py

import re

from database.db import get_session
from database.models import Subject, Assignment
from services.current_user import CurrentUser

DEFAULT_COLOR = "#2196F3"

COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SubjectService:

    @staticmethod
    def display_color(color):
        """
        Returns a saved color that's safe to put in a page's HTML: a hex
        color like "#2196F3", or the default for anything else.
        """

        if color and COLOR_PATTERN.match(color):
            return color

        return DEFAULT_COLOR

    @staticmethod
    def get_subject_assignment_count(subject_id):

        with get_session() as db:

            return (
                db.query(Assignment)
                .filter(
                    Assignment.subject_id == subject_id,
                    Assignment.family_id
                    == CurrentUser.get_family_id(),
                    Assignment.active.is_(True)
                )
                .count()
            )

    @staticmethod
    def get_subject_by_id(subject_id):

        with get_session() as db:

            return (
                db.query(Subject)
                .filter(
                    Subject.id == subject_id,
                    Subject.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

    @staticmethod
    def get_subjects_by_family(family_id):

        with get_session() as db:
            return (
                db.query(Subject)
                .filter(Subject.family_id == family_id)
                .filter(
                    Subject.active.is_(True)
                )
                .all()
            )

    @staticmethod
    def get_current_family_subjects():

        family_id = (
            CurrentUser.get_family_id()
        )

        return (
            SubjectService.get_subjects_by_family(
                family_id
            )
        )

    @staticmethod
    def create_subject(
        name,
        color=None
    ):

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            subject = Subject(
                family_id=CurrentUser.get_family_id(),
                name=name,
                color=SubjectService.display_color(color)
            )

            db.add(subject)
            db.commit()
            db.refresh(subject)

            return subject

    @staticmethod
    def update_subject(
        subject_id,
        name=None,
        color=None
    ):

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            subject = (
                db.query(Subject)
                .filter(
                    Subject.id == subject_id,
                    Subject.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

            if not subject:
                return None

            if name is not None:
                subject.name = name

            if color is not None:
                subject.color = SubjectService.display_color(color)

            db.commit()

            return subject

    @staticmethod
    def get_archived_subjects():
        """
        Returns the current family's archived subjects, by name, for a parent.
        """

        if not CurrentUser.is_parent():
            return []

        with get_session() as db:

            return (
                db.query(Subject)
                .filter(
                    Subject.family_id == CurrentUser.get_family_id(),
                    Subject.active.is_(False)
                )
                .order_by(Subject.name)
                .all()
            )

    @staticmethod
    def restore_subject(subject_id):
        """
        Unarchives a subject, so it can be chosen for new work again. Returns
        it, or None if it isn't available to this parent.
        """

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            subject = (
                db.query(Subject)
                .filter(
                    Subject.id == subject_id,
                    Subject.family_id == CurrentUser.get_family_id()
                )
                .first()
            )

            if not subject:
                return None

            subject.active = True

            db.commit()

            return subject

    @staticmethod
    def archive_subject(subject_id):

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            subject = (
                db.query(Subject)
                .filter(
                    Subject.id == subject_id,
                    Subject.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

            if not subject:
                return None

            subject.active = False

            db.commit()

            return subject
