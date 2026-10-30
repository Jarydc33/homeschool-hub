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

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
