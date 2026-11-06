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
    Keeps the login tokens in the browser's localStorage.

    Only the browser can reach localStorage, and it replies after the script
    has run. So each operation stops the script until the reply arrives, which
    triggers a rerun. Nothing moves on until the browser has confirmed.
    """

    TOKEN_STATE = "browser_session_token"
    REFRESH_TOKEN_STATE = "browser_session_refresh_token"
    DEVICE_TOKEN_STATE = "browser_session_device_token"
    PENDING_STATE = "browser_session_pending"
    REQUEST_STATE = "browser_session_request"

    @staticmethod
    def _perform(action, token=None, refresh_token=None, device_token=None):
        """
        Runs an action in the browser and returns what's saved there.
        Stops the script until the browser has replied.
        """

        request = st.session_state.get(
            SessionService.REQUEST_STATE,
            0
        )

        result = _browser_session(
            action=action,
            token=token,
            refresh_token=refresh_token,
            device_token=device_token,
            request=request,
            key=f"browser_session_{request}",
            default=None
        )

        if not result or result.get("request") != request:
            st.stop()

        st.session_state[
            SessionService.REQUEST_STATE
        ] = request + 1

        return result

    @staticmethod
    def get_access_token():
        """
        Returns the saved token, reading it from the browser once per session.
        """

        if SessionService.TOKEN_STATE not in st.session_state:

            saved = SessionService._perform("read")

            st.session_state[
                SessionService.TOKEN_STATE
            ] = saved.get("token")

            st.session_state[
                SessionService.REFRESH_TOKEN_STATE
            ] = saved.get("refresh_token")

            st.session_state[
                SessionService.DEVICE_TOKEN_STATE
            ] = saved.get("device_token")

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
    def get_known_refresh_token():
        """
        Returns the refresh token if it's already known, without asking
        the browser.
        """

        return st.session_state.get(
            SessionService.REFRESH_TOKEN_STATE
        )

    @staticmethod
    def save_session(access_token, refresh_token=None):
        """
        Queues saving the tokens. They're written on the next call to
        sync_browser, so follow this with st.rerun() or a page change.
        """

        st.session_state[
            SessionService.TOKEN_STATE
        ] = access_token

        st.session_state[
            SessionService.REFRESH_TOKEN_STATE
        ] = refresh_token

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "save",
            "token": access_token,
            "refresh_token": refresh_token
        }

    @staticmethod
    def clear_session():
        """
        Queues removing the tokens. They're removed on the next call to
        sync_browser, so follow this with st.rerun().
        """

        SessionService.forget_session()

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "clear"
        }

    @staticmethod
    def forget_session():
        """
        Stops using the tokens for the rest of this session, without
        touching the browser.
        """

        st.session_state[
            SessionService.TOKEN_STATE
        ] = None

        st.session_state[
            SessionService.REFRESH_TOKEN_STATE
        ] = None

    @staticmethod
    def get_device_token():
        """
        Returns a paired device's key, if it's known. It's read from the
        browser with the login tokens, so call this after get_access_token,
        as looking up the current user does.
        """

        return st.session_state.get(
            SessionService.DEVICE_TOKEN_STATE
        )

    @staticmethod
    def save_device_token(device_token):
        """
        Queues saving a paired device's key. Like save_session, follow this
        with st.rerun() or a page change.
        """

        st.session_state[
            SessionService.DEVICE_TOKEN_STATE
        ] = device_token

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "save_device",
            "device_token": device_token
        }

    @staticmethod
    def clear_device_token():
        """
        Queues removing a paired device's key. Follow this with st.rerun().
        """

        st.session_state[
            SessionService.DEVICE_TOKEN_STATE
        ] = None

        st.session_state[
            SessionService.PENDING_STATE
        ] = {
            "action": "clear_device"
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
            pending.get("token"),
            pending.get("refresh_token"),
            pending.get("device_token")
        )

        del st.session_state[
            SessionService.PENDING_STATE
        ]

        return pending["action"]
