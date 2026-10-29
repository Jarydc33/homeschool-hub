import streamlit as st
from services.startup_service import (
    initialize_database,
    database_is_empty
)
from scripts.seed_data import seed_database

# Initialize local SQLite database
initialize_database()

# Load demo data for first-time deployments
if database_is_empty():
    seed_database()

st.set_page_config(
    page_title="Homeschool Hub",
    page_icon="🏡",
    layout="wide"
)

st.title("🏡 Homeschool Hub")

st.write(
    """
    Welcome to Homeschool Hub.

    Use the navigation menu on the left to access pages.
    """
)