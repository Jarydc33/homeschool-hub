import hashlib
import logging
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

import streamlit as st
from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    DeviceMode,
    DeviceSession,
    PairingCode,
    Student,
    UserRole,
)
from services.student_mode_service import (
    FAILED_MESSAGE,
    LAST_SEEN_INTERVAL,
    StudentModeService,
)

logger = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^\d{6}$")

CODE_MINUTES = 10

# Wrong codes allowed in one browser session, and across the whole app, per
# GUESS_WINDOW. Every request comes from this server, so the app-wide limit
# is what really stops guessing: at most a few dozen guesses at a million
# codes, each of which only lives 10 minutes.
SESSION_GUESSES = 5

APP_GUESSES = 30

GUESS_WINDOW = timedelta(minutes=10)

SESSION_GUESSES_STATE = "pairing_wrong_codes"

WRONG_CODE_MESSAGE = (
    "That code didn't work. Check it, or ask a parent for a new one. "
    "Codes work once and expire after 10 minutes."
)

TOO_MANY_GUESSES_MESSAGE = (
    "Too many codes that didn't work. Please wait 10 minutes, then ask a "
    "parent for a new code."
)


@dataclass
class PairedUser:
    """
    Who a paired device is. It stands in for a users row, which students
    without email don't have, so AuthService's helpers work as usual.
    """

    device_session_id: int
    family_id: int
    family: object
    student_id: int
    student: object
    role: str = UserRole.STUDENT.value
    id: int = None
    email: str = None


@st.cache_resource
def _app_guesses():
    """Wrong codes across every session on this server, in memory."""

    return {
        "lock": threading.Lock(),
        "moments": [],
    }


def _hash(value):

    return hashlib.sha256(value.encode()).hexdigest()


class PairingService:
    """
    Pairs a student's own device with a one-time code, so it shows only
    their view without anyone's email or password on it.
    """

    # ----- Guess limits -----

    @staticmethod
    def _recent_app_guesses(store, now):

        store["moments"] = [
            moment
            for moment in store["moments"]
            if now - moment < GUESS_WINDOW
        ]

        return store["moments"]

    @staticmethod
    def too_many_guesses(now=None):
        """
        True when this browser session, or the app as a whole, has had too
        many wrong codes lately.
        """

        now = now or datetime.utcnow()

        session_guesses = [
            moment
            for moment in st.session_state.get(SESSION_GUESSES_STATE, [])
            if now - moment < GUESS_WINDOW
        ]

        if len(session_guesses) >= SESSION_GUESSES:
            return True

        store = _app_guesses()

        with store["lock"]:

            return len(
                PairingService._recent_app_guesses(store, now)
            ) >= APP_GUESSES

    @staticmethod
    def _record_wrong_guess(now):

        st.session_state[SESSION_GUESSES_STATE] = [
            moment
            for moment in st.session_state.get(SESSION_GUESSES_STATE, [])
            if now - moment < GUESS_WINDOW
        ] + [now]

        store = _app_guesses()

        with store["lock"]:

            PairingService._recent_app_guesses(store, now).append(now)

    @staticmethod
    def reset_guesses():
        """For tests."""

        st.session_state.pop(SESSION_GUESSES_STATE, None)

        store = _app_guesses()

        with store["lock"]:

            store["moments"].clear()

    # ----- Parents -----

    @staticmethod
    def create_code(
        student_id,
        now=None
    ):
        """
        Makes a one-time code that pairs a device to this student. Returns
        (code, expires_at, None), or (None, None, message). Parents only.
        """

        from services.current_user import CurrentUser

        if not CurrentUser.is_parent():
            return None, None, FAILED_MESSAGE

        if not StudentModeService.has_pin():
            return None, None, (
                "Please set a family PIN in Settings first. It's what "
                "unpairs a device."
            )

        now = now or datetime.utcnow()

        family_id = CurrentUser.get_family_id()

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id == family_id,
                    Student.active.is_(True)
                )
                .first()
            )

            if not student:
                return None, None, FAILED_MESSAGE

            # Two live codes can't match, or one would pair the wrong
            # student. Clashes are rare, so a few tries is plenty.

            for _ in range(20):

                code = f"{secrets.randbelow(1_000_000):06d}"

                clash = (
                    db.query(PairingCode)
                    .filter(
                        PairingCode.code_hash == _hash(code),
                        PairingCode.used_at.is_(None),
                        PairingCode.expires_at > now
                    )
                    .first()
                )

                if not clash:
                    break

            else:

                logger.warning("Couldn't find an unused pairing code")

                return None, None, FAILED_MESSAGE

            expires_at = now + timedelta(minutes=CODE_MINUTES)

            db.add(
                PairingCode(
                    family_id=family_id,
                    student_id=student.id,
                    code_hash=_hash(code),
                    created_by=CurrentUser.get().id,
                    created_at=now,
                    expires_at=expires_at
                )
            )

            db.commit()

        return code, expires_at, None

    # ----- The student's device -----

    @staticmethod
    def redeem(
        code,
        now=None
    ):
        """
        Pairs this device if the code is live. Returns (device_token, None)
        with the key to save in the browser, or (None, message).
        """

        now = now or datetime.utcnow()

        if PairingService.too_many_guesses(now):
            return None, TOO_MANY_GUESSES_MESSAGE

        code = (code or "").strip().replace(" ", "").replace("-", "")

        if not CODE_PATTERN.match(code):
            return None, "Please enter the 6-digit code."

        with get_session() as db:

            pairing = (
                db.query(PairingCode)
                .join(Student, Student.id == PairingCode.student_id)
                .filter(
                    PairingCode.code_hash == _hash(code),
                    PairingCode.used_at.is_(None),
                    PairingCode.expires_at > now,
                    Student.family_id == PairingCode.family_id,
                    Student.active.is_(True)
                )
                .first()
            )

            if not pairing:

                PairingService._record_wrong_guess(now)

                return None, WRONG_CODE_MESSAGE

            device_token = secrets.token_urlsafe(32)

            # The code is used up and the device saved in one commit, so a
            # code can never pair two devices.

            pairing.used_at = now

            db.add(
                DeviceSession(
                    family_id=pairing.family_id,
                    student_id=pairing.student_id,
                    mode=DeviceMode.PAIRED.value,
                    token_hash=_hash(device_token),
                    created_by=pairing.created_by,
                    created_at=now,
                    last_seen_at=now
                )
            )

            db.commit()

        return device_token, None

    @staticmethod
    def find_paired(
        device_token,
        now=None
    ):
        """
        Returns the PairedUser for a device's key, or None if it isn't
        paired, was ended, or its student is archived. Updates last_seen_at
        when it's more than a few minutes old.
        """

        if not device_token:
            return None

        now = now or datetime.utcnow()

        with get_session() as db:

            row = (
                db.query(DeviceSession)
                .options(
                    joinedload(DeviceSession.student)
                    .joinedload(Student.family)
                )
                .filter(
                    DeviceSession.token_hash == _hash(device_token),
                    DeviceSession.mode == DeviceMode.PAIRED.value,
                    DeviceSession.revoked_at.is_(None)
                )
                .first()
            )

            if (
                not row
                or not row.student.active
                or row.student.family_id != row.family_id
            ):
                return None

            if now - row.last_seen_at > LAST_SEEN_INTERVAL:

                row.last_seen_at = now

                db.commit()

            return PairedUser(
                device_session_id=row.id,
                family_id=row.family_id,
                family=row.student.family,
                student_id=row.student_id,
                student=row.student
            )

    @staticmethod
    def unpair(
        pin,
        now=None
    ):
        """
        Unpairs this device if the family PIN is right, and queues removing
        its key. Returns (unpaired, message). Follow success with st.rerun().
        """

        from services.auth_service import AuthService
        from services.current_user import CurrentUser
        from services.session_service import SessionService

        user = CurrentUser.get()

        if not isinstance(user, PairedUser):
            return False, FAILED_MESSAGE

        unpaired, message = StudentModeService.end_with_pin(
            user.device_session_id,
            user.family_id,
            pin,
            now
        )

        if not unpaired:
            return False, message

        SessionService.clear_device_token()

        AuthService.start_page_run()

        return True, "This device is unpaired."
