from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_setting

DATABASE_URL = get_setting("DATABASE_URL")

if DATABASE_URL.startswith("sqlite"):
    
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False
        }
    )

else:

    engine = create_engine(
        DATABASE_URL
    )

# expire_on_commit=False keeps a saved object's values readable after its
# session closes, since services return ORM objects to the pages.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine
)

Base = declarative_base()


@contextmanager
def get_session():
    """Opens a session and always closes it. Anything not committed is rolled back."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
