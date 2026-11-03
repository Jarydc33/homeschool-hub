# services/subject_service.py

from database.db import SessionLocal
from database.models import Subject, Assignment
from services.auth_service import AuthService

class SubjectService:

    @staticmethod
    def get_subject_assignment_count(subject_id):

        db = SessionLocal()

        try:

            return (
                db.query(Assignment)
                .filter(
                    Assignment.subject_id == subject_id
                )
                .count()
            )

        finally:
            db.close()

    @staticmethod
    def get_subject_by_id(subject_id):

        db = SessionLocal()

        try:

            return (
                db.query(Subject)
                .filter(Subject.id == subject_id)
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_subjects_by_family(family_id):

        db = SessionLocal()

        try:
            return (
                db.query(Subject)
                .filter(Subject.family_id == family_id)
                .filter(
                    Subject.active.is_(True)
                )
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def get_current_family_subjects():

        family_id = (
            AuthService.get_current_family()
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

        db = SessionLocal()

        try:

            subject = Subject(
                family_id=AuthService.get_current_family(),
                name=name,
                color=color
            )

            db.add(subject)
            db.commit()
            db.refresh(subject)

            return subject

        finally:
            db.close()

    @staticmethod
    def update_subject(
        subject_id,
        name=None,
        color=None
    ):

        db = SessionLocal()

        try:

            subject = (
                db.query(Subject)
                .filter(Subject.id == subject_id)
                .first()
            )

            if not subject:
                return None

            if name is not None:
                subject.name = name

            if color is not None:
                subject.color = color

            db.commit()

            return subject

        finally:
            db.close()

    @staticmethod
    def archive_subject(subject_id):

        db = SessionLocal()

        try:

            subject = (
                db.query(Subject)
                .filter(Subject.id == subject_id)
                .first()
            )

            if not subject:
                return None

            subject.active = False

            db.commit()

            return subject

        finally:
            db.close()