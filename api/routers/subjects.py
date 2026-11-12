from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_parent, signed_in
from api.errors import could_not_save, not_found
from api.schemas import Name
from services.subject_service import SubjectService

router = APIRouter(prefix="/subjects", tags=["subjects"])

NOT_FOUND_MESSAGE = "This subject could not be found."


class SubjectDetail(BaseModel):
    id: int
    name: str
    color: str | None
    assignment_count: int


class SubjectIn(BaseModel):
    name: Name
    # A hex color such as "#4f8a8b". Anything else is saved as no color.
    color: str | None = Field(default=None, max_length=20)


def _detail(subject, count=None):

    return SubjectDetail(
        id=subject.id,
        name=subject.name,
        color=subject.color,
        assignment_count=(
            count
            if count is not None
            else SubjectService.get_subject_assignment_count(subject.id)
        ),
    )


@router.get("", response_model=list[SubjectDetail])
def list_subjects(user=Depends(signed_in)):
    """The family's active subjects, with how many active assignments each has."""

    return [_detail(subject) for subject in SubjectService.get_current_family_subjects()]


@router.get("/archived", response_model=list[SubjectDetail])
def list_archived(user=Depends(require_parent)):

    return [_detail(subject) for subject in SubjectService.get_archived_subjects()]


@router.post("", response_model=SubjectDetail, status_code=201)
def create_subject(body: SubjectIn, user=Depends(require_parent)):

    subject = SubjectService.create_subject(body.name, body.color)

    if not subject:
        raise could_not_save()

    return _detail(subject, 0)


@router.put("/{subject_id}", response_model=SubjectDetail)
def update_subject(subject_id: int, body: SubjectIn, user=Depends(require_parent)):

    subject = SubjectService.update_subject(subject_id, body.name, body.color)

    if not subject:
        raise not_found(NOT_FOUND_MESSAGE)

    return _detail(subject)


@router.post("/{subject_id}/archive", response_model=SubjectDetail)
def archive_subject(subject_id: int, user=Depends(require_parent)):
    """
    Hides a subject from new work. Its assignments and grades stay as they
    are.
    """

    subject = SubjectService.archive_subject(subject_id)

    if not subject:
        raise not_found(NOT_FOUND_MESSAGE)

    return _detail(subject)


@router.post("/{subject_id}/restore", response_model=SubjectDetail)
def restore_subject(subject_id: int, user=Depends(require_parent)):

    subject = SubjectService.restore_subject(subject_id)

    if not subject:
        raise not_found(NOT_FOUND_MESSAGE)

    return _detail(subject)
