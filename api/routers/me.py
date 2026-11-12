from fastapi import APIRouter, Depends

from api.auth import signed_in
from api.schemas import Me
from services.current_user import CurrentUser
from services.pairing_service import PairedUser

router = APIRouter(tags=["me"])


@router.get("/me", response_model=Me)
def me(user=Depends(signed_in)):
    """Who is signed in, and how the app should treat them."""

    family = user.family

    if CurrentUser.is_admin():
        role = "admin"
    elif CurrentUser.is_student():
        role = "student"
    else:
        role = "parent"

    return Me(
        role=role,
        family_id=CurrentUser.get_family_id(),
        family_name=family.family_name if family else None,
        timezone=family.timezone if family else None,
        student_id=CurrentUser.get_student_id(),
        student_mode=CurrentUser.get_student_mode() is not None,
        paired_device=isinstance(user, PairedUser),
        today=CurrentUser.get_today(),
    )
