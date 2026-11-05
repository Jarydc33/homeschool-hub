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
    Time,
    UniqueConstraint,
    Uuid,
    false,
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
    CURRICULUM = "Curriculum"

class RecurrencePattern(Enum):

    DAILY = "Every Day"

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

    # How often recurring work happens, or a curriculum's school days, such
    # as "Mon,Tue,Wed,Thu".
    recurrence_pattern = Column(String)

    # When one-time work is due, or the first date of recurring work.
    due_date = Column(
        Date,
        nullable=False
    )

    # The last possible date of recurring work. Empty for one-time work.
    end_date = Column(Date)

    # Whether its work gets scores that count towards grades.
    graded = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false()
    )

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
    """Says who is assigned. Progress on each date is in AssignmentOccurrence."""

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

    # Points earned is score, and it's out of points_possible. Both are empty
    # until it's graded.
    points_possible = Column(Numeric(6, 2))

    # Which lesson this is, for curriculum work. It stays with the lesson when
    # the date moves.
    lesson_number = Column(Integer)

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

class Event(Base):
    """
    Something on a family's calendar. With no event_students it's for the
    whole family.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    description = Column(Text)

    # The event's date, or its first one.
    start_date = Column(
        Date,
        nullable=False
    )

    # The last day of a multi-day event. Empty otherwise.
    end_date = Column(Date)

    # Local to the family. Empty means all day.
    start_time = Column(Time)

    # How often it repeats, and the last possible date. Empty if it doesn't.
    recurrence_pattern = Column(String)

    repeat_until = Column(Date)

    active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    event_students = relationship(
        "EventStudent",
        back_populates="event",
        cascade="all, delete-orphan"
    )

class EventStudent(Base):
    """Says which students an event is for."""

    __tablename__ = "event_students"

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "student_id",
            name="uq_event_students_event_student"
        ),
    )

    id = Column(Integer, primary_key=True)

    event_id = Column(
        Integer,
        ForeignKey("events.id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    event = relationship(
        "Event",
        back_populates="event_students"
    )

    student = relationship("Student")

class Book(Base):
    """A book one student is reading or has read."""

    __tablename__ = "books"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    author = Column(String)

    total_pages = Column(Integer)

    # Empty means still reading.
    finished_on = Column(Date)

    active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    student = relationship("Student")

    logs = relationship(
        "ReadingLog",
        back_populates="book"
    )

class ReadingLog(Base):
    """How many pages of a book were read on one date."""

    __tablename__ = "reading_logs"

    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "log_date",
            name="uq_reading_logs_book_date"
        ),
    )

    id = Column(Integer, primary_key=True)

    book_id = Column(
        Integer,
        ForeignKey("books.id"),
        nullable=False
    )

    log_date = Column(
        Date,
        nullable=False
    )

    pages = Column(
        Integer,
        nullable=False
    )

    book = relationship(
        "Book",
        back_populates="logs"
    )

class GradingPeriod(Base):
    """
    A stretch of a family's school year, like Fall 2026. A grade belongs to
    the period its date falls in.
    """

    __tablename__ = "grading_periods"

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
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

class ActivityLog(Base):
    """One P.E. activity a student did on one date."""

    __tablename__ = "activity_logs"

    __table_args__ = (
        Index(
            "ix_activity_logs_student_date",
            "student_id",
            "log_date"
        ),
    )

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id"),
        nullable=False,
        index=True
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False
    )

    log_date = Column(
        Date,
        nullable=False
    )

    activity = Column(
        String,
        nullable=False
    )

    minutes = Column(
        Integer,
        nullable=False
    )

    student = relationship("Student")

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