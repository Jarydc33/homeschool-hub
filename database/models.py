from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import configure_mappers, relationship

from database.db import Base

DEFAULT_TIMEZONE = "America/Chicago"


class UserRole(str, Enum):
    PARENT = "Parent"
    STUDENT = "Student"
    ADMIN = "Admin"


class AssignmentStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETE = "Complete"


class AssignmentType(str, Enum):
    ONE_TIME = "One Time"
    RECURRING = "Recurring"

class RecurrencePattern(Enum):

    DAILY = "Daily"

    WEEKLY = "Weekly"

    MONTHLY = "Monthly"

    WEEKDAYS = "Weekdays"

    EVERY_MONDAY = "Every Monday"

    EVERY_TUESDAY = "Every Tuesday"

    EVERY_WEDNESDAY = "Every Wednesday"

    EVERY_THURSDAY = "Every Thursday"

    EVERY_FRIDAY = "Every Friday"

class Family(Base):
    __tablename__ = "families"

    id = Column(Integer, primary_key=True)

    family_name = Column(
        String,
        nullable=False
    )

    # An IANA name. "Today" for this family is the date in this zone.
    timezone = Column(
        String,
        nullable=False,
        default=DEFAULT_TIMEZONE,
        server_default=DEFAULT_TIMEZONE
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    users = relationship(
        "User",
        back_populates="family"
    )

    students = relationship(
        "Student",
        back_populates="family"
    )

    subjects = relationship(
        "Subject",
        back_populates="family"
    )

    assignments = relationship(
        "Assignment",
        back_populates="family"
    )

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # NULL only for Admins, who don't belong to a family.
    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=True
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    # The user's Supabase account. This is what identifies them at login;
    # email is only how they sign in, and it can change.
    auth_user_id = Column(
        Uuid(as_uuid=False),
        unique=True,
        nullable=False
    )

    password_hash = Column(String)

    role = Column(
        String,
        default=UserRole.PARENT.value
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    family = relationship(
        "Family",
        back_populates="users"
    )

    student = relationship(
        "Student"
    )

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    grade_level = Column(String)

    birth_year = Column(Integer)

    active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    family = relationship(
        "Family",
        back_populates="students"
    )

    student_assignments = relationship(
        "StudentAssignment",
        back_populates="student"
    )

    occurrences = relationship(
        "AssignmentOccurrence",
        back_populates="student"
    )

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    color = Column(String)

    active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    family = relationship(
        "Family",
        back_populates="subjects"
    )

    assignments = relationship(
        "Assignment",
        back_populates="subject"
    )

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    subject_id = Column(
        Integer,
        ForeignKey("subjects.id"),
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    description = Column(Text)

    assignment_type = Column(
        String,
        default=AssignmentType.ONE_TIME.value
    )

    recurrence_pattern = Column(String)

    due_date = Column(Date)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    family = relationship(
        "Family",
        back_populates="assignments"
    )

    subject = relationship(
        "Subject",
        back_populates="assignments"
    )

    student_assignments = relationship(
        "StudentAssignment",
        back_populates="assignment"
    )

    occurrences = relationship(
        "AssignmentOccurrence",
        back_populates="assignment"
    )

    active = Column(
        Boolean,
        default=True
    )

class StudentAssignment(Base):
    __tablename__ = "student_assignments"

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "student_id",
            name="student_assignments_assignment_id_student_id_key"
        ),
    )

    id = Column(Integer, primary_key=True)

    assignment_id = Column(
        Integer,
        ForeignKey("assignments.id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    status = Column(
        String,
        default=AssignmentStatus.NOT_STARTED.value
    )

    completed_at = Column(DateTime)

    notes = Column(Text)

    assignment = relationship(
        "Assignment",
        back_populates="student_assignments"
    )

    student = relationship(
        "Student",
        back_populates="student_assignments"
    )

class AssignmentOccurrence(Base):
    """One assignment, for one student, on one date."""

    __tablename__ = "assignment_occurrences"

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "student_id",
            "occurrence_date",
            name="uq_assignment_occurrences_assignment_student_date"
        ),
        Index(
            "ix_assignment_occurrences_student_date",
            "student_id",
            "occurrence_date"
        ),
    )

    id = Column(Integer, primary_key=True)

    assignment_id = Column(
        Integer,
        ForeignKey("assignments.id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    occurrence_date = Column(
        Date,
        nullable=False
    )

    status = Column(
        String,
        nullable=False,
        default=AssignmentStatus.NOT_STARTED.value,
        server_default=AssignmentStatus.NOT_STARTED.value
    )

    completed_at = Column(DateTime)

    notes = Column(Text)

    score = Column(Numeric(6, 2))

    assignment = relationship(
        "Assignment",
        back_populates="occurrences"
    )

    student = relationship(
        "Student",
        back_populates="occurrences"
    )

class BannerMessage(Base):
    __tablename__ = "banner_messages"

    id = Column(
        Integer,
        primary_key=True
    )

    # The family this announcement belongs to.
    # NULL means it's system-wide, created by an Admin.
    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=True,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    message = Column(
        Text,
        nullable=False
    )

    start_date = Column(
        Date,
        nullable=False
    )

    end_date = Column(
        Date,
        nullable=False
    )

    active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

class CurrentSession:

    user_id = None

    family_id = None

    role = None

    student_id = None


# Link the relationships now instead of on the first query. When deployed files
# change, Streamlit forgets these modules, and a script still running can query
# with the old classes after the others are gone. Unlinked, that raises
# "expression 'Family' failed to locate a name".
configure_mappers()