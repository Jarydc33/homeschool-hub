from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.db import Base


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

    family_id = Column(
        Integer,
        ForeignKey("families.id")
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
        ForeignKey("families.id")
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

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)

    family_id = Column(
        Integer,
        ForeignKey("families.id")
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
        ForeignKey("families.id")
    )

    subject_id = Column(
        Integer,
        ForeignKey("subjects.id")
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

    active = Column(
        Boolean,
        default=True
    )

class StudentAssignment(Base):
    __tablename__ = "student_assignments"

    id = Column(Integer, primary_key=True)

    assignment_id = Column(
        Integer,
        ForeignKey("assignments.id")
    )

    student_id = Column(
        Integer,
        ForeignKey("students.id")
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
        nullable=True
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