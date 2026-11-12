import logging
import re
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    DeviceMode,
    DeviceSession,
    Family,
    Student,
)

logger = logging.getLogger(__name__)

PIN_PATTERN = re.compile(r"^\d{4}$")

MAX_PIN_ATTEMPTS = 5

LOCK_MINUTES = 5

# How stale last_seen_at can get before a page run updates it, so every
# click doesn't write to the database.
LAST_SEEN_INTERVAL = timedelta(minutes=5)

WRONG_PIN_MESSAGE = "That PIN isn't right. Please try again."

LOCKED_MESSAGE = (
    "Too many wrong tries, so the PIN is locked for a few minutes. "
    "Please wait and try again."
)

FAILED_MESSAGE = (
    "Something went wrong. Please refresh the page and try again."
)


class StudentModeService:
    """
    Student Mode switches a parent's login to one student's view until the
    family PIN is entered. The mode is stored against the Supabase session,
    so clearing or editing the browser can't end it.
    """

    @staticmethod
    def describe_time(
        moment,
        zone
    ):
        """
        Returns a saved UTC time in the family's zone, like "Nov 6, 3:05 PM".
        """

        local = moment.replace(tzinfo=timezone.utc).astimezone(zone)

        hour = local.hour % 12 or 12

        return (
            f"{local:%b} {local.day}, "
            f"{hour}:{local:%M} {local:%p}"
        )

    @staticmethod
    def pin_error(pin):
        """
        Returns what's wrong with a new PIN for showing, or None.
        """

        if not PIN_PATTERN.match(pin or ""):
            return "Please enter exactly 4 digits."

        return None

    @staticmethod
    def has_pin():
        """
        True if the current family has set a PIN.
        """

        from services.current_user import CurrentUser

        family_id = CurrentUser.get_family_id()

        if not family_id:
            return False

        with get_session() as db:

            family = db.get(Family, family_id)

            return bool(family and family.parent_pin_hash)

    @staticmethod
    def set_pin(
        pin,
        confirm_pin
    ):
        """
        Saves the family's PIN. Returns (saved, message). Parents only, and
        not from inside Student Mode.
        """

        from services.current_user import CurrentUser

        if not CurrentUser.is_parent():
            return False, FAILED_MESSAGE

        error = StudentModeService.pin_error(pin)

        if error:
            return False, error

        if pin != confirm_pin:
            return False, "The two PINs don't match."

        with get_session() as db:

            family = db.get(
                Family,
                CurrentUser.get_family_id()
            )

            if not family:
                return False, FAILED_MESSAGE

            family.parent_pin_hash = bcrypt.hashpw(
                pin.encode(),
                bcrypt.gensalt()
            ).decode()

            db.commit()

        return True, "PIN saved."

    @staticmethod
    def find_active(
        family_id,
        auth_session_id,
        now=None
    ):
        """
        Returns the Student Mode row for this login, with its student, or
        None. Updates last_seen_at when it's more than a few minutes old.
        """

        if not family_id or not auth_session_id:
            return None

        now = now or datetime.utcnow()

        with get_session() as db:

            row = (
                db.query(DeviceSession)
                .options(joinedload(DeviceSession.student))
                .filter(
                    DeviceSession.family_id == family_id,
                    DeviceSession.auth_session_id == auth_session_id,
                    DeviceSession.mode == DeviceMode.STUDENT_MODE.value,
                    DeviceSession.revoked_at.is_(None)
                )
                .order_by(DeviceSession.id.desc())
                .first()
            )

            if row and now - row.last_seen_at > LAST_SEEN_INTERVAL:

                row.last_seen_at = now

                db.commit()

                db.refresh(row)

                row.student

            return row

    @staticmethod
    def start(student_id):
        """
        Switches this login to the student's view. Returns (started, message).
        """

        from services.current_user import CurrentUser

        if not CurrentUser.is_parent():
            return False, FAILED_MESSAGE

        if not StudentModeService.has_pin():
            return False, "Please set a family PIN in Settings first."

        auth_session_id = CurrentUser.get_auth_session_id()

        if not auth_session_id:

            logger.warning("Student Mode couldn't find the login's session")

            return False, (
                "Student Mode couldn't start. Please log out, log back in, "
                "and try again."
            )

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
                return False, FAILED_MESSAGE

            db.add(
                DeviceSession(
                    family_id=family_id,
                    student_id=student.id,
                    mode=DeviceMode.STUDENT_MODE.value,
                    auth_session_id=auth_session_id,
                    created_by=CurrentUser.get().id
                )
            )

            db.commit()

            name = student.name

        CurrentUser.forget_student_mode()

        return True, f"Student Mode is on for {name}."

    @staticmethod
    def exit(pin, now=None):
        """
        Ends Student Mode on this login if the PIN is right. Returns
        (exited, message). Too many wrong tries lock the PIN for a while.
        """

        from services.current_user import CurrentUser

        mode = CurrentUser.get_student_mode()

        if not mode:
            return False, FAILED_MESSAGE

        exited, message = StudentModeService.end_with_pin(
            mode.id,
            mode.family_id,
            pin,
            now
        )

        if not exited:
            return False, message

        CurrentUser.forget_student_mode()

        return True, "Student Mode is off."

    @staticmethod
    def end_with_pin(
        device_session_id,
        family_id,
        pin,
        now=None
    ):
        """
        Ends one device's student view if the family PIN is right, for
        Student Mode or a paired device. Returns (ended, message). Too many
        wrong tries lock that device's PIN for a while.
        """

        now = now or datetime.utcnow()

        with get_session() as db:

            row = (
                db.query(DeviceSession)
                .filter(
                    DeviceSession.id == device_session_id,
                    DeviceSession.family_id == family_id,
                    DeviceSession.revoked_at.is_(None)
                )
                .first()
            )

            family = db.get(Family, family_id)

            if not row or not family or not family.parent_pin_hash:
                return False, FAILED_MESSAGE

            if row.locked_until and row.locked_until > now:
                return False, LOCKED_MESSAGE

            if PIN_PATTERN.match(pin or "") and bcrypt.checkpw(
                pin.encode(),
                family.parent_pin_hash.encode()
            ):

                row.revoked_at = now
                row.failed_pin_attempts = 0
                row.locked_until = None

                db.commit()

                return True, None

            row.failed_pin_attempts += 1

            if row.failed_pin_attempts >= MAX_PIN_ATTEMPTS:

                row.failed_pin_attempts = 0
                row.locked_until = now + timedelta(minutes=LOCK_MINUTES)

                db.commit()

                return False, LOCKED_MESSAGE

            db.commit()

            return False, WRONG_PIN_MESSAGE

    @staticmethod
    def end_current_for_logout():
        """
        Ends Student Mode on this login without the PIN. Only for logging
        out, which needs the parent's password to undo.
        """

        from services.current_user import CurrentUser

        mode = CurrentUser.get_student_mode()

        if not mode:
            return

        StudentModeService._revoke(mode.id, mode.family_id)

        CurrentUser.forget_student_mode()

    @staticmethod
    def list_sessions():
        """
        Returns the family's devices in Student Mode or paired, newest
        first, with their students. Parents only.
        """

        from services.current_user import CurrentUser

        if not CurrentUser.is_parent():
            return []

        with get_session() as db:

            return (
                db.query(DeviceSession)
                .options(joinedload(DeviceSession.student))
                .filter(
                    DeviceSession.family_id
                    == CurrentUser.get_family_id(),
                    DeviceSession.revoked_at.is_(None)
                )
                .order_by(DeviceSession.created_at.desc())
                .all()
            )

    @staticmethod
    def end_session(device_session_id):
        """
        Ends Student Mode or a pairing on another device. Returns True if
        it was ended. Parents only.
        """

        from services.current_user import CurrentUser

        if not CurrentUser.is_parent():
            return False

        return StudentModeService._revoke(
            device_session_id,
            CurrentUser.get_family_id()
        )

    @staticmethod
    def _revoke(
        device_session_id,
        family_id
    ):

        with get_session() as db:

            row = (
                db.query(DeviceSession)
                .filter(
                    DeviceSession.id == device_session_id,
                    DeviceSession.family_id == family_id,
                    DeviceSession.revoked_at.is_(None)
                )
                .first()
            )

            if not row:
                return False

            row.revoked_at = datetime.utcnow()

            db.commit()

            return True
