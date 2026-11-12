"""
Who is calling the API.

A signed-in parent or student sends their Supabase access token as
"Authorization: Bearer <token>". A paired student device has no login and
sends its device key as "X-Device-Token" instead. Every endpoint that needs
a user depends on signed_in (or require_parent), which runs the whole
request as that user through CurrentUser, so the services apply the same
family and role checks as in the Streamlit app.
"""
import logging

from fastapi import Depends, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from services.auth_provider import AuthProvider
from services.current_user import CurrentUser
from services.pairing_service import PairingService
from services.user_service import UserService

logger = logging.getLogger(__name__)

LOG_IN_MESSAGE = "Please log in again."

UNAVAILABLE_MESSAGE = "We couldn't check your login right now. Please try again in a moment."


def _bearer_token(authorization):

    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def identify(authorization, device_token):
    """
    Returns (user, auth_session_id) for a request, or (None, None) when
    there's no valid login. A login token wins over a device key. Blocking:
    it calls Supabase and the database.
    """

    access_token = _bearer_token(authorization)

    if access_token:

        auth_user = AuthProvider.get_auth_user_for_token(access_token)

        if not auth_user or not auth_user.user:
            logger.warning("Refused a login: Supabase rejected the token.")
            return None, None

        user = UserService.get_user_by_auth_id(auth_user.user.id)

        if not user:
            logger.warning("Refused a login: no Tally user for this account.")
            return None, None

        if UserService.is_archived_student(user):
            logger.warning("Refused a login: the student is archived.")
            return None, None

        return user, AuthProvider.session_id_from_token(access_token)

    if device_token:
        return PairingService.find_paired(device_token), None

    return None, None


async def signed_in(
    authorization: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
):
    """
    Requires a signed-in user and runs the rest of the request as them.

    This must stay async: a value set in a sync dependency doesn't reach the
    endpoint. The lookup itself runs in a worker thread.
    """

    try:

        user, auth_session_id = await run_in_threadpool(
            identify,
            authorization,
            x_device_token,
        )

    except Exception as ex:

        logger.warning("Checking a login failed: %s", type(ex).__name__)

        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            UNAVAILABLE_MESSAGE,
        )

    if user is None:

        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            LOG_IN_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        )

    with CurrentUser.acting_as(user, auth_session_id):
        yield user


PARENTS_ONLY_MESSAGE = "Only a parent can do this."


def require_parent(user=Depends(signed_in)):
    """
    Requires a parent, and not one whose login is in Student Mode. The
    services check this too; this gives a clear answer up front.
    """

    if not CurrentUser.is_parent():

        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            PARENTS_ONLY_MESSAGE,
        )

    return user
