from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os
import streamlit as st

load_dotenv()

#DATABASE_URL = "sqlite:///homeschool_hub.db"

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:
    DATABASE_URL = st.secrets["DATABASE_URL"]

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
