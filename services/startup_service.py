from database.db import Base, engine, SessionLocal
from database.models import Family


def initialize_database():
    """
    Creates all database tables if they don't exist.
    """
    Base.metadata.create_all(bind=engine)


def database_is_empty():
    """
    Returns True if no families exist.
    """

    db = SessionLocal()

    try:
        family_count = db.query(Family).count()
        return family_count == 0

    finally:
        db.close()