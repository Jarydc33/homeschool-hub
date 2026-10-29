# services/subject_service.py

from database.db import SessionLocal
from database.models import Subject


class SubjectService:

    @staticmethod
    def get_all_subjects():

        db = SessionLocal()

        try:
            return db.query(Subject).all()

        finally:
            db.close()

    @staticmethod
    def get_subject(subject_id):

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
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def create_subject(
        family_id,
        name,
        color=None
    ):

        db = SessionLocal()

        try:

            subject = Subject(
                family_id=family_id,
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