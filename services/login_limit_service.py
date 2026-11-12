import threading
from datetime import datetime, timedelta

MAX_FAILURES = 5

WINDOW = timedelta(minutes=15)

LOCKED_MESSAGE = (
    "Too many incorrect passwords for this email. Please wait 15 minutes "
    "and try again, or use \"Forgot your password?\" below."
)


# Failed logins per email, shared by every session in this server process.
# Every login reaches Supabase from this server's address, so Supabase's own
# per-address limit can't tell one guesser from all our families. Kept in
# memory: a restart (or Streamlit reloading modules on a deploy) clears it,
# which only resets the wait. An API running several processes would need it
# in the database instead.
_STORE = {
    "lock": threading.Lock(),
    "failures": {},
}


def _store():

    return _STORE


class LoginLimitService:

    @staticmethod
    def _key(email):

        return (email or "").strip().lower()

    @staticmethod
    def _recent(failures, now):

        return [
            moment
            for moment in failures
            if now - moment < WINDOW
        ]

    @staticmethod
    def is_locked(email, now=None):
        """
        True when this email has had too many wrong passwords lately, so
        the login shouldn't even be tried.
        """

        now = now or datetime.utcnow()

        store = _store()

        with store["lock"]:

            recent = LoginLimitService._recent(
                store["failures"].get(LoginLimitService._key(email), []),
                now
            )

            return len(recent) >= MAX_FAILURES

    @staticmethod
    def record_failure(email, now=None):

        now = now or datetime.utcnow()

        key = LoginLimitService._key(email)

        store = _store()

        with store["lock"]:

            # Forget emails whose failures have all expired, so the store
            # can't keep growing.

            for other in [
                other
                for other, moments in store["failures"].items()
                if not LoginLimitService._recent(moments, now)
            ]:
                del store["failures"][other]

            store["failures"][key] = LoginLimitService._recent(
                store["failures"].get(key, []),
                now
            ) + [now]

    @staticmethod
    def record_success(email):

        store = _store()

        with store["lock"]:

            store["failures"].pop(
                LoginLimitService._key(email),
                None
            )

    @staticmethod
    def reset():
        """For tests."""

        store = _store()

        with store["lock"]:

            store["failures"].clear()
