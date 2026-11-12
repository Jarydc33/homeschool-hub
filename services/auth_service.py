import streamlit as st

from services.account_service import AccountService
from services.current_user import CurrentUser
from services.user_service import UserService
from database.models import DEFAULT_TIMEZONE

from services.auth_provider import AuthProvider
from services.student_mode_service import StudentModeService
from services.pairing_service import PairedUser, PairingService
from services.session_service import (
    SessionService
)


# Holds the current user for one page run. Having no user is saved too, since
# looking that up can mean a call to Supabase.
USER_THIS_RUN = "current_user_this_run"

# Holds this login's Student Mode row, or None, for one page run.
MODE_THIS_RUN = "student_mode_this_run"


class AuthService:

    # Creating and changing logins lives in AccountService, which the API
    # shares. These keep the names pages already use.

    @staticmethod
    def register_parent(
        family_name,
        email,
        password,
        timezone=DEFAULT_TIMEZONE
    ):

        return AccountService.register_parent(
            family_name,
            email,
            password,
            timezone
        )

    @staticmethod
    def invite_student(student_id, email):

        return AccountService.invite_student(student_id, email)

    @staticmethod
    def update_student_email(student_id, new_email):

        return AccountService.update_student_email(student_id, new_email)

    @staticmethod
    def start_page_run():
        """
        Forgets the saved user, so this page run looks them up fresh. Run it
        before anything reads the current user. NavigationComponent.render()
        does, and so does app.py.

        A button in an open dialog reruns only the dialog, so it keeps the
        user from when the page last ran.
        """

        st.session_state.pop(
            USER_THIS_RUN,
            None
        )

        AuthService.forget_student_mode()

    @staticmethod
    def forget_student_mode():
        """
        Makes the next check look up Student Mode fresh, after it starts or
        ends.
        """

        st.session_state.pop(
            MODE_THIS_RUN,
            None
        )

    @staticmethod
    def get_auth_session_id():
        """
        Returns the Supabase session behind this login, or None.
        """

        return AuthProvider.session_id_from_token(
            SessionService.get_known_token()
        )

    @staticmethod
    def get_student_mode():
        """
        Returns this login's Student Mode row, with its student, or None.
        Only a parent's login can be in Student Mode. Looked up once per
        page run.
        """

        if MODE_THIS_RUN not in st.session_state:

            st.session_state[
                MODE_THIS_RUN
            ] = AuthService._load_student_mode()

        return st.session_state[
            MODE_THIS_RUN
        ]

    @staticmethod
    def _load_student_mode():

        return CurrentUser.load_student_mode(
            AuthService.get_current_user(),
            AuthService.get_auth_session_id()
        )

    @staticmethod
    def set_current_user(user_id):

        st.session_state[
            "current_user_id"
        ] = user_id

        AuthService.start_page_run()

    @staticmethod
    def is_archived_student(user):
        """
        True for a student login whose student has been archived.
        They can't sign in until the student is unarchived.
        """

        return UserService.is_archived_student(user)

    @staticmethod
    def _allow_login(user):
        """
        Returns the user, or None if their account can't be used.
        The flag lets the Login page explain why.
        """

        if user and AuthService.is_archived_student(user):

            st.session_state[
                "account_inactive"
            ] = True

            return None

        return user

    @staticmethod
    def get_current_user():
        """
        Returns the signed-in user, looking them up once per page run.
        """

        if USER_THIS_RUN not in st.session_state:

            st.session_state[
                USER_THIS_RUN
            ] = AuthService._load_current_user()

        return st.session_state[
            USER_THIS_RUN
        ]

    @staticmethod
    def _load_current_user():

        user_id = (
            st.session_state.get(
                "current_user_id"
            )
        )

        if user_id:

            return AuthService._allow_login(
                UserService.get_user_by_id(
                    user_id
                )
            )

        auth_user = (
            AuthProvider.get_current_auth_user()
        )

        if not auth_user:

            # No one's logged in, so this may be a student's paired device.

            return PairingService.find_paired(
                SessionService.get_device_token()
            )

        user = AuthService._allow_login(
            UserService.get_user_by_auth_id(
                auth_user.user.id
            )
        )

        if user:

            AuthService.set_current_user(
                user.id
            )

        return user

    @staticmethod
    def is_paired_device():
        """
        True on a student's paired device, which has no login.
        """

        return isinstance(
            AuthService.get_current_user(),
            PairedUser
        )

    # The role helpers live in CurrentUser, so services and API requests
    # share them. These keep the names pages already use.

    @staticmethod
    def is_authenticated():

        return CurrentUser.is_authenticated()

    @staticmethod
    def is_parent():

        return CurrentUser.is_parent()

    @staticmethod
    def is_student():

        return CurrentUser.is_student()

    @staticmethod
    def is_admin():

        return CurrentUser.is_admin()

    @staticmethod
    def get_current_family():

        return CurrentUser.get_family_id()

    @staticmethod
    def get_today():
        """
        Returns today's date for the current family (see CurrentUser).
        """

        return CurrentUser.get_today()

    @staticmethod
    def get_zone():

        return CurrentUser.get_zone()

    @staticmethod
    def get_current_student():

        return CurrentUser.get_student_id()

    @staticmethod
    def logout():
        """
        Ends the session in Supabase and here, and queues removing the token
        from the browser. Follow this with st.rerun().
        """

        # Logging out of Student Mode is allowed without the PIN, since
        # getting back in needs the parent's password.

        StudentModeService.end_current_for_logout()

        access_token = (
            SessionService.get_known_token()
        )

        if access_token:

            AuthProvider.sign_out(
                access_token,
                SessionService.get_known_refresh_token()
            )

        SessionService.clear_session()

        st.session_state.pop(
            "current_user_id",
            None
        )

        AuthService.start_page_run()


# Outside an API request, services ask AuthService who's signed in.

CurrentUser.set_fallback(AuthService)
