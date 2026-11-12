"""
Friendly errors. Each has a message the app can show as is; details stay in
the server log.
"""
from fastapi import HTTPException, status


def not_found(message="This could not be found."):
    """
    Missing, archived, or another family's: all look the same, so nobody can
    learn what exists in another family.
    """

    return HTTPException(status.HTTP_404_NOT_FOUND, message)


def invalid(message):
    """Something the person entered needs fixing."""

    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


def could_not_save(message="We couldn't save that. Please check it and try again."):
    """The service refused, for a reason the checks before it didn't catch."""

    return HTTPException(status.HTTP_400_BAD_REQUEST, message)
