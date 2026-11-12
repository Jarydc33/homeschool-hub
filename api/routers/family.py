import threading
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, StringConstraints

from api.auth import require_parent, signed_in
from api.errors import invalid, not_found
from api.schemas import Message, Name, StudentOut, student_out
from services.family_service import FamilyService
from services.pairing_service import GUESS_WINDOW, PairedUser, PairingService
from services.student_mode_service import StudentModeService

router = APIRouter(tags=["family"])

Pin = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10)]


class TimeZoneChoice(BaseModel):
    name: str
    label: str


class FamilySettings(BaseModel):
    family_name: str
    timezone: str
    has_pin: bool


class SettingsIn(BaseModel):
    family_name: Name
    timezone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class PinIn(BaseModel):
    pin: Pin
    confirm_pin: Pin


class PinOnly(BaseModel):
    pin: Pin


class StudentModeIn(BaseModel):
    student_id: int


class DeviceOut(BaseModel):
    id: int
    # "student_mode" or "paired".
    mode: str
    student: StudentOut
    created_at: datetime
    last_seen_at: datetime | None


class CodeIn(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]


class DeviceToken(BaseModel):
    """The key a paired device keeps and sends as X-Device-Token."""

    device_token: str


# ----- Settings -----


@router.get("/timezones", response_model=list[TimeZoneChoice])
def timezones():
    """Time zones for a dropdown, common ones first. Needs no login, for sign-up."""

    return [
        TimeZoneChoice(name=name, label=FamilyService.timezone_label(name))
        for name in FamilyService.timezone_choices()
    ]


@router.get("/family", response_model=FamilySettings)
def get_settings(user=Depends(require_parent)):

    family = user.family

    return FamilySettings(
        family_name=family.family_name,
        timezone=family.timezone,
        has_pin=StudentModeService.has_pin(),
    )


@router.put("/family", response_model=FamilySettings)
def update_settings(body: SettingsIn, user=Depends(require_parent)):
    """
    Saves the family's name and time zone. Saved dates don't change; only
    what counts as today does.
    """

    error = FamilyService.settings_error(body.family_name, body.timezone)

    if error:
        raise invalid(error)

    family = FamilyService.update_settings(body.family_name, body.timezone)

    if not family:
        raise invalid("These settings couldn't be saved.")

    return FamilySettings(
        family_name=family.family_name,
        timezone=family.timezone,
        has_pin=StudentModeService.has_pin(),
    )


@router.put("/family/pin", response_model=Message)
def set_pin(body: PinIn, user=Depends(require_parent)):
    """The 4-digit PIN that ends Student Mode and unpairs devices."""

    saved, message = StudentModeService.set_pin(body.pin, body.confirm_pin)

    if not saved:
        raise invalid(message)

    return Message(message=message)


# ----- Student Mode and devices -----


@router.post("/student-mode", response_model=Message)
def start_student_mode(body: StudentModeIn, user=Depends(require_parent)):
    """
    Switches this login to one student's view until the family PIN is
    entered. Needs a PIN set first.
    """

    started, message = StudentModeService.start(body.student_id)

    if not started:
        raise invalid(message)

    return Message(message=message)


@router.post("/student-mode/exit", response_model=Message)
def exit_student_mode(body: PinOnly, user=Depends(signed_in)):
    """Back to the parent's view, with the family PIN. Wrong tries are limited."""

    exited, message = StudentModeService.exit(body.pin)

    if not exited:
        raise invalid(message)

    return Message(message=message)


@router.post("/logout", response_model=Message)
def logout(user=Depends(signed_in)):
    """
    Call before signing out of Supabase. Ends Student Mode on this login
    without the PIN, since getting back in needs the parent's password.
    """

    StudentModeService.end_current_for_logout()

    return Message(message="Logged out.")


@router.get("/family/devices", response_model=list[DeviceOut])
def list_devices(user=Depends(require_parent)):
    """Devices in Student Mode or paired, newest first."""

    return [
        DeviceOut(
            id=row.id,
            mode=row.mode,
            student=student_out(row.student),
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
        )
        for row in StudentModeService.list_sessions()
    ]


@router.post("/family/devices/{device_id}/end", response_model=Message)
def end_device(device_id: int, user=Depends(require_parent)):

    if not StudentModeService.end_session(device_id):
        raise not_found("This device could not be found.")

    return Message(message="Device ended.")


# ----- Paired devices -----

# Wrong codes per client address, in memory. PairingService also limits
# wrong codes app-wide. Behind a proxy, run uvicorn with --proxy-headers so
# the address is the device's, not the proxy's.
_GUESSES = {}
_GUESSES_LOCK = threading.Lock()


def _client_guesses(request):

    key = request.client.host if request.client else "unknown"

    now = datetime.utcnow()

    with _GUESSES_LOCK:

        # Forget clients whose wrong codes have all expired.

        for other in [
            other
            for other, moments in _GUESSES.items()
            if all(now - moment >= GUESS_WINDOW for moment in moments)
        ]:
            del _GUESSES[other]

        return _GUESSES.setdefault(key, [])


@router.post("/pairing/redeem", response_model=DeviceToken)
def redeem_pairing_code(body: CodeIn, request: Request):
    """
    Pairs this device with a code a parent made. Needs no login. Keep the
    returned key safely on the device and send it as X-Device-Token.
    """

    device_token, message = PairingService.redeem(
        body.code,
        client_guesses=_client_guesses(request),
    )

    if not device_token:
        raise invalid(message)

    return DeviceToken(device_token=device_token)


@router.post("/pairing/unpair", response_model=Message)
def unpair(body: PinOnly, user=Depends(signed_in)):
    """Unpairs this device with the family PIN. Then forget its key."""

    if not isinstance(user, PairedUser):
        raise invalid("This device isn't paired.")

    unpaired, message = StudentModeService.end_with_pin(
        user.device_session_id,
        user.family_id,
        body.pin,
    )

    if not unpaired:
        raise invalid(message)

    return Message(message="This device is unpaired.")


def reset_guesses():
    """For tests."""

    with _GUESSES_LOCK:
        _GUESSES.clear()
