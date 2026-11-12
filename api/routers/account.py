"""
Signing up. Logging in, password resets and invite links happen in the app
with Supabase's own client; the API only needs to know who's signed in.
"""
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, StringConstraints

from api.errors import invalid
from api.schemas import Name
from database.models import DEFAULT_TIMEZONE
from services.account_service import AccountService
from services.family_service import FamilyService

router = APIRouter(tags=["account"])

MIN_PASSWORD_LENGTH = 8


class RegisterIn(BaseModel):
    family_name: Name
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
    password: Annotated[str, StringConstraints(max_length=200)]
    timezone: str = DEFAULT_TIMEZONE


class Registered(BaseModel):
    """
    With email confirmation on, Supabase gives no session until the email
    is confirmed: confirm_email is true and the tokens are empty.
    """

    confirm_email: bool
    access_token: str | None = None
    refresh_token: str | None = None


@router.post("/register", response_model=Registered, status_code=201)
def register(body: RegisterIn):
    """Creates a Supabase account, a family, and its first parent."""

    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise invalid(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    timezone = FamilyService.preferred_timezone(body.timezone)

    user, session, error = AccountService.register_parent(
        body.family_name,
        body.email,
        body.password,
        timezone,
    )

    if error:
        raise invalid(error)

    if not session:
        return Registered(confirm_email=True)

    return Registered(
        confirm_email=False,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
    )
