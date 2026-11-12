"""
App settings, read from environment variables (or a local .env file).

The Streamlit app on Streamlit Cloud keeps them in st.secrets instead, so
that's checked last, and only if Streamlit is installed. Everything else
(the API, scripts, tests) uses environment variables and never imports
Streamlit.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class MissingSettingError(RuntimeError):
    pass


def get_setting(name):
    """
    Returns a setting's value. Raises MissingSettingError, naming the
    setting but never showing any value, if it isn't set anywhere.
    """

    value = os.getenv(name)

    if value:
        return value

    value = _from_streamlit_secrets(name)

    if value:
        return value

    raise MissingSettingError(
        f"{name} is not set. Add it to .env or the host's environment."
    )


def _from_streamlit_secrets(name):

    try:
        import streamlit as st
    except ImportError:
        return None

    try:
        return st.secrets[name]
    except Exception:
        # No secrets file, or no such key.
        return None
