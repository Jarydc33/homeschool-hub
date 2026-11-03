import os

import streamlit as st
import streamlit.components.v1 as components

_browser_session = components.declare_component(
    "browser_session",
    path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "components",
        "browser_session"
    )
)


class SessionService:
    """
    Keeps the login token in the browser's localStorage.

    Only the browser can reach localStorage, and it replies after the script
    has run. So each operation stops the script until the reply arrives, which
    triggers a rerun. Nothing moves on until the browser has confirmed.
    """

    TOKEN_STATE = "browser_session_token"
    PENDING_STATE = "browser_session_pending"
    REQUEST_STATE = "browser_session_request"

    @staticmethod
    def _perform(action, token=None):
        """
        Runs an action in the browser and returns the token saved there.
        Stops the script until the browser has replied.
        """

        request = st.session_state.get(
            SessionService.REQUEST_STATE,
            0
        )

        result = _browser_session(
            action=action,
            token=token,
            request=request,
            key=f"browser_session_{request}",
            default=None
        )

        if not result or result.get("request") != request:
            st.stop()

        st.session_state[
            SessionService.REQUEST_STATE
        ] = request + 1

        return result.get("token")

    @staticmethod
    def get_access_token():
        """
        Returns the saved token, reading it from the browser once per session.
        """

        if SessionService.TOKEN_STATE not in st.session_state:

            st.session_state[
                SessionService.TOKEN_STATE
            ] = SessionService._perform("read")

        return st.session_state[
            SessionService.TOKEN_STATE
        ]

    @staticmethod
    def get_known_token():
        """
        Returns the token if it's already known, without asking the browser.
        Safe to use while handling a button click, which a stop would lose.
        """

        return st.session_state.get(
            SessionService.TOKEN_STATE
        )

    @staticmethod
    def save_session(access_token):
        """
        Queues saving the token. It's written on the next call to
        sync_browser, so follow this with st.rerun() or a page change.
        """

        st.session_state[
            SessionService.TOKEN_STATE
        ] = access_token

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "save",
            "token": access_token
        }

    @staticmethod
    def clear_session():
        """
        Queues removing the token. It's removed on the next call to
        sync_browser, so follow this with st.rerun().
        """

        st.session_state[
            SessionService.TOKEN_STATE
        ] = None

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "clear"
        }

    @staticmethod
    def sync_browser():
        """
        Finishes any queued write, stopping the script until it's confirmed.
        Returns the action that just finished, or None.
        """

        pending = st.session_state.get(
            SessionService.PENDING_STATE
        )

        if not pending:
            return None

        SessionService._perform(
            pending["action"],
            pending.get("token")
        )

        del st.session_state[
            SessionService.PENDING_STATE
        ]

        return pending["action"]
