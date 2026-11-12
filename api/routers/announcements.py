from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.auth import signed_in
from api.errors import could_not_save, invalid, not_found
from api.schemas import Banner, LongText, Title, banner
from services.banner_service import BannerService
from services.current_user import CurrentUser

router = APIRouter(prefix="/announcements", tags=["announcements"])

NOT_FOUND_MESSAGE = "This announcement could not be found."


class BannerIn(BaseModel):
    title: Title
    message: LongText
    # It shows from start_date through end_date.
    start_date: date
    end_date: date


def require_manager(user=Depends(signed_in)):
    """Parents manage their family's announcements; Admins system-wide ones."""

    if not (CurrentUser.is_parent() or CurrentUser.is_admin()):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a parent can manage announcements.",
        )

    return user


def _check(body):

    if not body.message:
        raise invalid("Please enter a message.")

    if body.end_date < body.start_date:
        raise invalid("The end date must be on or after the start date.")


@router.get("", response_model=list[Banner])
def list_announcements(user=Depends(require_manager)):
    """Every announcement this person manages, including ones not showing now."""

    return [banner(row) for row in BannerService.get_manageable_banners()]


@router.post("", response_model=Banner, status_code=201)
def create_announcement(body: BannerIn, user=Depends(require_manager)):

    _check(body)

    row = BannerService.create_banner(
        body.title, body.message, body.start_date, body.end_date
    )

    if not row:
        raise could_not_save()

    return banner(row)


@router.put("/{banner_id}", response_model=Banner)
def update_announcement(banner_id: int, body: BannerIn, user=Depends(require_manager)):

    _check(body)

    row = BannerService.update_banner(
        banner_id, body.title, body.message, body.start_date, body.end_date
    )

    if not row:
        raise not_found(NOT_FOUND_MESSAGE)

    return banner(row)


@router.post("/{banner_id}/archive", response_model=Banner)
def archive_announcement(banner_id: int, user=Depends(require_manager)):

    row = BannerService.archive_banner(banner_id)

    if not row:
        raise not_found(NOT_FOUND_MESSAGE)

    return banner(row)
